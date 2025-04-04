import asyncio
import json
import random
import anycaptcha
import httpx
import pandas as pd
from asyncio import Semaphore
from collections import deque
from datetime import datetime, timezone
from functools import partialmethod
from json import JSONDecodeError
from curl_cffi.requests import RequestsError
from eth_account import Account
from eth_utils import to_checksum_address
from anycaptcha import Solver, Service
from tabulate import tabulate

from examples.dex.evm.sahara.db import SaharaAccount
from examples.dex.evm.sahara.models import TextQuestion, SingleChoiceQuestion
from examples.dex.evm.sahara.utils import (
    recover_public_key, SaharaAI_Testnet, db_helper, abi, contract_address, update_exam_storage, gpt_client,
    answers_storage, exam_system_messages, parse_requirement_bitmap, review_system_messages, Conversation, offset,
    retry_count, text_label_type_system_messages
)
from examples.dex.evm.sahara.utils import data_path
from web3mt.consts import Web3mtENV
from web3mt.dex.models import DEX
from web3mt.onchain.evm.client import BaseEVMClient
from web3mt.utils import my_logger as logger, CustomAsyncSession, sleep

Account.enable_unaudited_hdwallet_features()


class SaharaClient(DEX):
    MAIN_DOMAIN = 'https://app.saharalabs.ai'
    API_URL = f'{MAIN_DOMAIN}/api'
    GRAPHQL_URL = 'https://graphql.saharaa.info/subgraphs/name/DataService'
    CURRENT_SEASON_NAME = 'Data Services - Season 3'

    def __init__(self, account: SaharaAccount, save_session: bool = True):
        self._sp = 0
        self._exp = 0
        self.account = account
        session = CustomAsyncSession(proxy=account.proxy, headers={'Referer': 'https://app.saharalabs.ai/'})
        if self.account.session_token:
            session.headers.update({'Authorization': f'Bearer {self.account.session_token}'})
        session.config.log_info = str(account.account_id)
        client = BaseEVMClient(
            Account.from_key(account.private) if account.private.startswith('0x') or ' ' not in account.private else
            Account.from_mnemonic(account.private),
            chain=SaharaAI_Testnet, proxy=account.proxy
        )
        super().__init__(session, client)
        self.level_achievement_manager_contract = (
            self.client.w3.eth.contract(to_checksum_address(contract_address), abi=abi)
        )
        self.user_info = dict()
        self.save_session = save_session
        self.conversations = dict()
        self.tasks_stat = dict()

    def __str__(self):
        return f'{self.account.account_id} | {self.client.account.address}'

    def __repr__(self):
        return self.__str__()

    async def __aenter__(self):
        await super().__aenter__()
        if not await self.profile():
            return
        await self.all_seasons_points()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger.error(f'{self} | {exc_val}')
        if self.tasks_stat:
            self._show_and_save_stats()
        if self.save_session:
            await db_helper.edit(self.account)
        await super().__aexit__(exc_type, exc_val, exc_tb)

    @property
    def sp(self):
        return self._sp

    @sp.setter
    def sp(self, value):
        self._sp = value

    @property
    def exp(self):
        return self._exp

    @exp.setter
    def exp(self, value):
        self._exp = value

    async def _generate_message(self):
        try:
            _, data = await self.session.post(
                f'{self.MAIN_DOMAIN}/v1/auth/generate-message',
                json={'address': self.client.account.address, 'chainId': hex(SaharaAI_Testnet.chain_id)}
            )
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        data = data.get('data')
        if data['ipAllowed']:
            return data['message']
        else:
            logger.warning(f'{self} | IP {self.client.proxy} not allowed')

    def _show_and_save_stats(self):
        df = pd.DataFrame.from_dict(self.tasks_stat, orient='index').reset_index()
        df.rename(columns={'index': 'Task'}, inplace=True)
        df = df[[
            "Task", "role", "difficulty", "submitted", "waiting_review", "approved", 'sp_per_dp',
            "accuracy", "dp_left", "earned", "workload_type"
        ]]
        df.rename(columns={
            'Task': f'{self.account.account_id} | {str(datetime.now())}',
            'role': 'Role',
            'difficulty': 'Difficulty',
            'submitted': 'Submitted',
            'waiting_review': 'Waiting Review',
            'approved': 'Approved',
            'sp_per_dp': 'SP/DP',
            'accuracy': 'Accuracy',
            'dp_left': 'DP Left',
            'earned': 'Earned',
            'workload_type': 'Is Limit Reached'
        }, inplace=True)
        df['Accuracy'] = df['Accuracy'].apply(lambda x: f'{x:.2f}%' if x else None)
        df['Earned'] = df['Earned'].apply(lambda x: f'{x} SP')
        df['Is Limit Reached'] = df['Is Limit Reached'].apply(lambda x: True if x in [2, 5, 7] else False)
        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False))
        df.to_csv(data_path / 'stats' / f'{self.account.account_id}.csv', index=False)

    async def _solve_captcha(self, url: str) -> str | None:
        solver = Solver(Service.TWOCAPTCHA, Web3mtENV.TWO_CAPTCHA_API_KEY)
        logger.info(f'{self} | Solving captcha')
        for i in range(retry_count):
            try:
                solved = await solver.solve_recaptcha_v2(
                    site_key='6LddMRwqAAAAABCvraXuK1zkUN6CEnRRiTdp9dgT',
                    page_url=url,
                )
                break
            except (
                    httpx.HTTPStatusError, anycaptcha.errors.UnableToSolveError, httpx.RemoteProtocolError,
                    anycaptcha.errors.SolutionWaitTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadError
            ) as e:
                logger.warning(f'{self} | Error when solving captcha. {e}. Trying again {i + 1}/{retry_count}')
                await sleep(10, 30)
        else:
            return
        logger.info(f'{self} | Captcha solved')
        return solved.solution.token

    async def login(self) -> bool:
        if not (message := await self._generate_message()):
            return False
        signature = self.client.sign(message)
        pubkey = recover_public_key(message, signature)
        try:
            _, data = await self.session.post(f'{self.MAIN_DOMAIN}/v1/auth/login', json=dict(
                message=message, pubkey=pubkey, signature='0x' + signature, role=7, walletType="io.rabby"
            ))
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return False
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return False
        logger.debug(f'{self} | Logged in')
        data = data.get('data')
        token = data['token']
        self.user_info = data['user']
        self.account.session_token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        return True

    async def profile(self):
        while True:
            try:
                _, data = await self.session.get(f'{self.API_URL}/users/v3/profile')
                break
            except RequestsError as e:
                self.session.headers.pop('Authorization', None)
                if not (await self.login()):
                    return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        data = data.get('data')
        self.user_info = data
        return data

    async def all_seasons_points(self):
        try:
            _, data = await self.session.get(f'{self.API_URL}/vault/seasons')
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        seasons = data.get('data')
        total_sp = 0
        for season in seasons:
            if season['name'] == self.CURRENT_SEASON_NAME:
                self.exp = season['userExp']
            total_sp += season['userPoints']
            logger.info(f'{self} | {season["name"]}. {season["userPoints"]} SP, {season["userExp"]} EXP')
        logger.debug(f'{self} | Total: {total_sp} SP. Current EXP: {self.exp}')
        self.sp = total_sp
        return True

    async def in_progress_achievements(self):
        _, data = await self.session.get(f'{self.API_URL}/achievement/in-progress')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        return data['data']

    async def claim_in_progress_achievements(self):
        seasons = await self.in_progress_achievements()
        for season in seasons:
            for achievement in season['achievementDTOS']:
                user_achievement = achievement['userAchievement']
                achievement_info = achievement['achievement']
                achievement_id = achievement_info['id']
                achievement_name = achievement_info['name']
                if achievement_name in ["Titan’s Vigil", "Forge of Perseverance"]:
                    for requirement_id in parse_requirement_bitmap(
                            user_achievement['requirementBitmap'], user_achievement['onChainRequirementBitmap']
                    ):
                        await self.claim_exp_process(achievement_name, achievement_id, requirement_id)
        await self.check_achievements_level()
        logger.success(f'{self} | Claimed all in-progress achievements')

    async def claim_exp_process(self, achievement_name: str, achievement_id: int, requirement_number: int):
        if not await self.client.balance_of():
            logger.warning(f'{self} | No balance, can\'t claim')
            return
        exp, increased_exp, level = (
                await self.prepare_claim_exp(achievement_id, requirement_number) or (None, None, None)
        )
        if not exp:
            return
        if not (sig := await self.proofs_level(exp, level)):
            logger.warning(f'{self} | No signature to claim EXP for achievement "{achievement_name}"')
            return
        if not (tx_hash := await self.claim_exp_onchain(level, exp, sig)):
            return
        await sleep(10, echo=True, log_info=f'{self}')
        if await self.sync_claim_exp(tx_hash):
            logger.success(f'{self} | Claimed {increased_exp} EXP for {achievement_name}. Total EXP: {exp}')

    async def prepare_claim_exp(self, achievement_id: int, requirement_number: int) -> tuple[int, int, int] | None:
        _, data = await self.session.post(f'{self.API_URL}/achievement/prepare-claim-exp', json=dict(
            achievementId=achievement_id, requirementNo=requirement_number
        ))
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            return data['exp'], data['increasedExp'], data['level']

    async def proofs_level(self, exp: int, level: int, can_upgrade: bool | None = None) -> str | None:
        _, data = await self.session.post(
            f'{self.API_URL}/proofs/level',
            json=dict(exp=exp, level=level) | (dict(canUpgrade=can_upgrade) if can_upgrade else {})
        )
        if data := data.get('data'):
            return data['sig']

    async def claim_exp_onchain(self, level: int, exp: int, sig: str):
        ok, tx_hash = await self.client.tx(
            self.level_achievement_manager_contract.address, 'Claim EXP',
            self.level_achievement_manager_contract.encode_abi('upgradeLevel', args=[level, exp, sig])
        )
        if ok:
            return tx_hash

    async def sync_claim_exp(self, tx_hash: str) -> bool:
        _, data = await self.session.post(f'{self.API_URL}/achievement/sync-claim-exp', json={'hash': tx_hash})
        return data['data']

    async def check_achievements_level(self):
        _, data = await self.session.get(f'{self.API_URL}/achievement/profile')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        data = data.get('data')
        current_level = data['onChainLevel']
        claimed_level = data['claimedLevel']
        claimed_exp = data['claimedExp']
        while current_level < claimed_level:
            if not (sig := await self.proofs_level(claimed_exp, current_level, can_upgrade=True)):
                return
            if not (tx_hash := await self.claim_exp_onchain(current_level, claimed_exp, sig)):
                return
            await sleep(10, log_info=f'{self}', echo=True)
            if await self.sync_level_up(tx_hash):
                current_level += 1
                logger.success(f'{self} | Claimed level {current_level}')
        logger.debug(f'{self} | Current level: {current_level}, current EXP: {claimed_exp}')
        return current_level

    async def sync_level_up(self, tx_hash: str) -> bool:
        _, data = await self.session.post(f'{self.API_URL}/users/sync-levelup', json={'hash': tx_hash})
        return data['data']

    async def mint_in_progress_achievements(self):
        seasons = await self.in_progress_achievements()
        for season in seasons:
            for achievement in season['achievementDTOS']:
                user_achievement = achievement['userAchievement']
                achievement_info = achievement['achievement']
                achievement_id = achievement_info['id']
                achievement_name = achievement_info['name']
                achievement_mint_start = datetime.fromisoformat(
                    achievement_info['mintStartAt']
                ) if achievement_info['mintStartAt'] else datetime.min.replace(tzinfo=timezone.utc)
                achievement_mint_end = datetime.fromisoformat(
                    achievement_info['mintEndAt']
                ) if achievement_info['mintEndAt'] else datetime.max.replace(tzinfo=timezone.utc)
                if (
                        user_achievement['passed'] and
                        not user_achievement['onChainPassed'] and
                        achievement_mint_start < datetime.now(tz=timezone.utc) < achievement_mint_end
                ):
                    await self.mint_achievement_proccess(achievement_name, user_achievement['level'], achievement_id)
        logger.success(f'{self} | Minted all in-progress achievements')

    async def mint_achievement_proccess(self, achievement_name: str, level: int, achievement_id: int):
        if not await self.client.balance_of():
            logger.warning(f'{self} | No balance, can\'t claim')
            return
        if not (sig := await self.proofs_achievements(0, level, achievement_id)):
            logger.warning(f'{self} | No signature to mint achievement "{achievement_name}"')
            return
        if not (tx_hash := await self.mint_achievement_onchain(achievement_id, level, 0, sig, achievement_name)):
            return
        await sleep(10, echo=True, log_info=f'{self}')
        if await self.sync_achievement_claimed(tx_hash, achievement_id):
            logger.success(f'{self} | Minted "{achievement_name}" achievement')

    async def proofs_achievements(
            self, exp: int, level: int, platform_achievement_id: int, enable_estimate: bool = True
    ):
        try:
            _, data = await self.session.post(f'{self.API_URL}/proofs/achievements', json=dict(
                exp=exp, level=level, platformAchievementId=platform_achievement_id, enableEstimate=enable_estimate
            ))
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return
        if data := data.get('data'):
            return data['sig']

    async def mint_achievement_onchain(
            self, achievement_id: int, level: int, exp: int, sig: str, achievement_name: str
    ):
        ok, tx_hash = await self.client.tx(
            self.level_achievement_manager_contract.address, f'Mint {achievement_name}',
            self.level_achievement_manager_contract.encode_abi('safeMint', args=[achievement_id, level, exp, sig])
        )
        if ok:
            return tx_hash

    async def sync_achievement_claimed(self, tx_hash: str, achievement_id: int) -> bool | None:
        _, data = await self.session.post(
            f'{self.API_URL}/achievement/sync-achievement-claimed',
            json=dict(hash=tx_hash, achievementId=achievement_id)
        )
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        return data['success']

    async def get_tasks(self, status: str):
        _, data = await self.session.get(
            f'{self.API_URL}/jobs/jobs',
            params=dict(sortType='createdAtDesc', jobType='individual', status=status, limit=20, page=1)
        )
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            data = data['data']
            return data

    get_in_progress_tasks = partialmethod(get_tasks, "Active")
    get_closed_tasks = partialmethod(get_tasks, "Complete")

    async def do_tasks(self):
        await self.apply_new_tasks()
        await self.do_in_progress_tasks(review=True, annotate=True)

    async def apply_new_tasks(self):
        while tasks := await self.get_new_tasks():
            task = tasks[0]
            task_name = task['job']['name']
            exam_status = (task.get('userRequirementStatus') or [{}])[0].get('status', 0)
            if exam_status == 0:
                if requirements := task['requirements']:
                    await self.take_exam_gpt(requirements[0]['relationId'], task_name)
            await self.join_task(task['job']['id'], task_name)
            await sleep(30, log_info=f'{self}', echo=True)
        await update_exam_storage()

    async def get_new_tasks(self):
        _, data = await self.session.get(
            f'{self.API_URL}/jobs/market/individuals', params=dict(sortType='earliest', limit=20, page=1)
        )
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            data = data['data']
            for task in data:
                if task['userRequirementStatus'] and task['userRequirementStatus'][0]['status'] == 2:
                    data.remove(task)
            logger.info(f'{self} | Got {len(data)} new tasks')
            return data

    async def join_task(self, task_id: int, task_name: str = None):
        _, data = await self.session.post(f'{self.API_URL}/jobs/join/{task_id}/individual')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        data = data['data']
        role = data['role']
        logger.debug(f'{self} | Joined task "{task_name}" ({task_id}) as "{role}"')

    async def take_exam_gpt(self, exam_id: int, task_name: str = None):
        await self.join_exam(exam_id)
        await self.get_exam_status(exam_id)
        questions, task_id = await self.get_exam_questions_and_task_id(exam_id)
        answers = list()
        question_and_answers = dict()
        for i, question in enumerate(questions):
            question_string = question['question'].strip()
            question_id = question['id']
            details = json.loads(question['details'])
            options = details['options']

            answer, index = await self._get_answer_to_question_index_gpt(
                SingleChoiceQuestion(question=question_string, options=options), exam_id
            )
            if not answer:
                return
            question_and_answers[question_string] = answer
            answers.append(dict(questionId=question_id, answer=index, explanation=""))
        await sleep(15, 30, log_info=f'{self}', echo=True)
        accuracy = await self.submit_exam_answers(exam_id, task_id, answers, task_name)
        if accuracy and accuracy == 100 and str(exam_id) not in answers_storage:
            answers_storage[exam_id] = question_and_answers

    async def join_exam(self, exam_id: int):
        _, data = await self.session.post(f'{self.API_URL}/individuals/join/{exam_id}/exam')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            return data

    async def get_exam_status(self, exam_id: int) -> bool | None:
        _, data = await self.session.get(f'{self.API_URL}/individuals/exam/{exam_id}/status')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            return data

    async def get_exam_task_id(self, exam_id: int):
        _, data = await self.session.post(f'{self.API_URL}/individuals/exam/{exam_id}/tasks')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            return data[0]['task']['id']

    async def submit_exam_answers(self, exam_id: int, task_id: int, answers: list[dict], task_name: str = None):
        _, data = await self.session.post(f'{self.API_URL}/individuals/exam/{exam_id}/submit-answers', json=dict(
            data=[dict(submitAnswer=dict(answers=answers, feedback=''), taskId=task_id)]
        ))
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            accuracy = float(data['content']) / 100
            logger.debug(f'{self} | Exam for "{task_name}" ({task_id}) passed. Accuracy: {accuracy:.2f}%')
            return accuracy

    async def get_exam_questions_and_task_id(self, exam_id: int) -> tuple[list[dict], int] | None:
        _, data = await self.session.get(f'{self.API_URL}/batches/{exam_id}/labeling-tasks')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if data := data.get('data'):
            return data[0]['tasks'][0]['questions'], data[0]['tasks'][0]['task']['id']

    async def do_in_progress_tasks(self, review: bool = True, annotate: bool = False):
        q = deque(await self.get_in_progress_tasks())
        while q:
            task = q.popleft()
            job_id = task['job']['id']
            role = task['user']['role']
            if not (job_data := await self.get_job(job_id)):
                continue
            job_name = job_data['job']['name']
            if role == 'Labeler':
                sp_per_dp = job_data['batch']['annotatingPrice']
            else:
                sp_per_dp = job_data['batch']['reviewingPrice']
            approved_count = job_data['approvedCount']
            earned = job_data['earning']
            submitted_count = job_data['submittedCount']
            waiting_review_count = job_data['waitingReviewCount']
            accuracy = None
            if submitted_count and submitted_count - waiting_review_count != 0:
                accuracy = (approved_count / (submitted_count - waiting_review_count)) * 100
            datapoints_left = job_data['jobLeftTaskCount']
            workload_type = job_data['workloadType']
            difficulty = job_data['batch']['difficulty']
            label_type = job_data['batch']['labelType']
            if workload_type == 5:
                additional_info = '. Limit reached'
            elif workload_type in [9, 10]:
                additional_info = '. This account is unable to claim data points from this task'
            else:
                additional_info = ''
            s = (
                    f'{self} | Task "{job_name}". Role: "{role}". '
                    f'{approved_count} approved, {submitted_count} submitted, {waiting_review_count} waiting review count. ' +
                    (f'Accuracy: {accuracy:.2f}%. ' if accuracy else '') +
                    f'SP/DP: {sp_per_dp}. Earned: {earned} SP. Datapoints left: {datapoints_left}' +
                    additional_info
            )
            self.tasks_stat[job_name] = {
                'role': role, 'difficulty': difficulty, 'workload_type': workload_type,
                'approved': approved_count, 'submitted': submitted_count, 'waiting_review': waiting_review_count,
                'accuracy': accuracy, 'earned': earned, 'dp_left': datapoints_left, 'sp_per_dp': sp_per_dp
            }
            if workload_type == 5:
                logger.debug(s)
                continue
            elif workload_type in [9, 10]:
                logger.warning(s)
                continue
            else:
                logger.info(s)
            if role == 'Labeler':
                min_time_seconds = job_data['batch']['annotatingMinDatapointSecond']
                if difficulty in [
                    'beginner', 'intermediate',
                    # 'advanced'
                ] and annotate:
                    if not datapoints_left:
                        logger.info(f'{self} | No DP for "{job_name}" ({job_id}), role "{role}"')
                        q.append(task)
                    else:
                        if await self.do_label_task(job_id, job_name, min_time_seconds, label_type) is not False:
                            q.append(task)
                else:
                    logger.info(
                        f'{self} | Skipping task with role "{role}" and difficulty "{difficulty}" for "{job_name}"'
                    )
            elif role == 'Reviewer':
                min_time_seconds = job_data['batch']['reviewingMinDatapointSecond']
                if review:
                    if not datapoints_left:
                        logger.info(f'{self} | No DP for "{job_name}" ({job_id}), role "{role}"')
                        q.append(task)
                    else:
                        if await self.do_review_task(job_id, job_name, min_time_seconds) is not False:
                            q.append(task)
                else:
                    logger.info(
                        f'{self} | Skipping task with role "{role}" and difficulty "{difficulty}" for "{job_name}"'
                    )
            await sleep(15, 30, log_info=f'{self}', echo=True)

    async def get_job(self, job_id: int):
        try:
            _, data = await self.session.get(f'{self.API_URL}/jobs/{job_id}/individual')
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if not (data := data.get('data')):
            logger.warning(f'{self} | No job data. Maybe something went wrong')
            return
        return data

    async def _get_answer_to_question_index_gpt(
            self, choice_question: SingleChoiceQuestion, id_: int = None, find_in_storage: bool = True,
            task_description: str = None
    ) -> tuple[str, int] | None:
        if find_in_storage and (answer := answers_storage.get(str(id_), {}).get(choice_question.question)):
            try:
                return answer, choice_question.options.index(answer)
            except ValueError:
                pass
        for i in range(retry_count * 3):
            try:
                if task_description:
                    choice_question_str = f'{task_description} {choice_question}'
                else:
                    choice_question_str = f'{choice_question}'
                response = await gpt_client.chat.completions.create(
                    model="gpt-4o-mini", web_search=False, stream=False, proxy=Web3mtENV.ROTATING_PROXY,
                    messages=(exam_system_messages + [{"role": "user", "content": choice_question_str}]),
                )
                answer = response.choices[0].message.content.strip()
                index = choice_question.options.index(answer)
                return answer, index
            except Exception as e:
                logger.warning(f'{self} | {e.args[0]}. Trying again {i + 1}/{retry_count}')
                await sleep(5, 10, log_info=f'{self}', echo=True)
        logger.error(f'{self} | No answer for question {choice_question}')

    async def do_label_task(self, job_id: int, job_name: str, min_time_seconds: int, label_type: str):
        async def do_context_label_task():
            self.conversations[job_id] = Conversation(
                task_description=current_task_description, questions=text_questions, offset=offset
            )
            j = 0
            while True:
                try:
                    response = await self.conversations[job_id].get_response()
                    gpt_answers = response.split('\n\n')
                except Exception as e:
                    logger.warning(f'{self} | Problem with GPT. {e.args[0]}. Trying again {j + 1}/{retry_count}')
                    await sleep(5, 10, log_info=f'{self}', echo=True)
                    return
                if len(gpt_answers) != len(text_questions):
                    self.conversations[job_id] = Conversation(
                        task_description=current_task_description, questions=text_questions, offset=offset
                    )
                else:
                    break
            submit_answers[i]['submitAnswer']['answers'] = submit_answers[i]['submitAnswer'].get('answers', []) + [
                dict(answer=gpt_answers[k], explanation='', questionId=required_questions[k]['id'])
                for k in range(len(required_questions))
            ]

        async def do_text_label_task():
            choice_question = choice_questions[0]
            for j in range(retry_count):
                try:
                    response = await gpt_client.chat.completions.create(
                        model="gpt-4o-mini", web_search=False, stream=False, proxy=Web3mtENV.ROTATING_PROXY,
                        messages=(text_label_type_system_messages + [{
                            "role": "user",
                            "content": f'{current_task_description}\n{choice_question}\n\n' + '\n'.join([
                                f'{q.question} Answer in {q.min_length}-{q.max_length} characters'
                                for q in text_questions
                            ])}])
                    )
                    gpt_answers = response.choices[0].message.content.strip().split('\n\n')
                    choice_answer = gpt_answers[0].strip().removesuffix('.')
                    index = choice_question.options.index(choice_answer)
                    text_answer = ' '.join(gpt_answers[1:]).strip()
                    if len(text_answer) < 100:
                        raise ValueError(f'Text answer is too short - {len(text_answer)} characters')
                    break
                except Exception as e:
                    logger.warning(f'{self} | Problem with GPT. {e.args[0]}. Trying again {j + 1}/{retry_count}')
                    await sleep(5, 10, log_info=f'{self}', echo=True)
            submit_answers[i]['submitAnswer']['answers'] = []
            for question in required_questions:
                if question['questionType'] == 'text':
                    submit_answers[i]['submitAnswer']['answers'].append(
                        dict(answer=text_answer, explanation='', questionId=question['id']))
                elif question['questionType'] == 'single_choice':
                    submit_answers[i]['submitAnswer']['answers'].append(
                        dict(answer=str(index), explanation='', questionId=question['id']))

        questions = await self.get_questions(job_id)
        honey_pot_data = await self.get_annotating_answers(job_id, job_name)
        if not honey_pot_data:
            return honey_pot_data
        submit_hp_answers, submit_answers, hp_data, task_descriptions = honey_pot_data
        required_questions = [question for question in questions if question['answerRequired']]
        text_questions = []
        choice_questions = []
        for question in required_questions:
            question_type = question['questionType']
            question_string = question['question']
            details = json.loads(question['details'])
            if question_type == 'text':
                min_length = details['minLength']
                max_length = details['maxLength']
                text_questions.append(
                    TextQuestion(question=question_string, min_length=min_length, max_length=max_length)
                )
            elif question_type == 'single_choice':
                options = details['options']
                choice_questions.append(SingleChoiceQuestion(question=question_string, options=options))

        if len(choice_questions) > 1:  # если в одном блоке вопросов несколько вопросов с вариантами ответов
            pass
        for i in range(len(submit_hp_answers)):  # block of answers
            if label_type == 'context':
                current_task_description = task_descriptions[0]
                await do_context_label_task()
            elif label_type == 'text':
                current_task_description = task_descriptions[i]
                await do_text_label_task()
            else:
                ...
            hp_question = SingleChoiceQuestion(question=hp_data[i]['question'], options=hp_data[i]['options'])
            answer, index = await self._get_answer_to_question_index_gpt(hp_question, job_id)
            submit_hp_answers[i]['submitAnswer'] = str(index)
            time = 0
            for k in range(len(required_questions)):
                if i > 0 and k == 0:
                    duration = random.randint(min_time_seconds * 1000, (min_time_seconds + 10) * 1000)
                else:
                    duration = 0
                duration += random.randint(5000, 15000)
                time += duration
            submit_answers[i]['time'] = time
        await sleep(min_time_seconds * len(submit_answers) + random.randint(5, 20), log_info=f'{self}', echo=True)
        await self.submit_annotating(submit_answers, submit_hp_answers, job_name, job_id)

    async def do_review_task(self, job_id: int, job_name: str, min_time_seconds: int):
        questions = await self.get_questions(job_id)
        answers_data = await self.get_review_answers(job_id, job_name)
        if not answers_data:
            return answers_data
        hp_reviews, answers_set, reviews = answers_data
        text_questions = []
        required_questions = [question for question in questions if question['answerRequired']]
        for question in required_questions:
            text_questions.append(question['question'])
        for i, (answers, review) in enumerate(zip(answers_set, reviews)):
            text_answers = []
            if answers:
                for j, answer in enumerate(answers):
                    text_answers.append(answer['answer'])
                for j in range(retry_count):
                    try:
                        response = await gpt_client.chat.completions.create(
                            model="gpt-4o-mini", web_search=False, stream=False, proxy=Web3mtENV.ROTATING_PROXY,
                            messages=(review_system_messages + [{
                                "role": "user",
                                "content": '\n'.join([f'{q}. {a}' for q, a in zip(text_questions, text_answers)])
                            }]),
                        )
                    except Exception as e:
                        logger.warning(f'{self} | Problem with GPT. {e.args[0]}. Trying again {j + 1}/{retry_count}')
                        await sleep(5, 10, log_info=f'{self}', echo=True)
                        continue
                    response = response.choices[0].message.content.lower().strip().split(',')
                    try:
                        gpt_answers = [json.loads(answer) for answer in response]
                        break
                    except JSONDecodeError as e:
                        logger.info(f'{self} | GPT return bad answer - {response}. Trying again {j + 1}/{retry_count}')
            else:
                gpt_answers = [False] * len(text_questions)
            time = 0
            question_reviews = []
            for j, (answer, question) in enumerate(zip(gpt_answers, questions)):
                if i > 0 and j == 0:
                    duration = random.randint(min_time_seconds * 1000, (min_time_seconds + 10) * 1000)
                else:
                    duration = 0
                duration += random.randint(1000, 5000)
                time += duration
                question_reviews.append(dict(approve=answer, comment="", duration=duration, questionId=question['id']))
            review['time'] = time
            review['questionReviews'] = question_reviews
        await sleep(min_time_seconds * len(reviews) + random.randint(5, 20), log_info=f'{self}', echo=True)
        await self.submit_review(hp_reviews, reviews, job_name, job_id)

    async def get_questions(self, job_id: int) -> list[dict] | None:
        _, data = await self.session.get(f'{self.API_URL}/jobs/{job_id}/labeling-tasks')
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if not (data := data.get('data')):
            logger.warning(f'{self} | No labeling tasks for job. Maybe something went wrong')
            return
        data = data[0]
        questions = data['tasks'][0]['questions']
        return questions

    async def get_review_answers(self, job_id: int, task_name: str) -> tuple[list, list, list] | bool | None:
        try:
            _, data = await self.session.get(f'{self.API_URL}/jobs/{job_id}/take-review-jobs/for-individuals')
        except RequestsError as e:
            if 'User workloads exceeded' in str(e):
                logger.debug(f'{self} | Limit reached for "{task_name}" (Reviewer) task')
                return False
            else:
                logger.error(f'{self} | {e}')
                return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if not (data := data.get('data')):
            logger.info(f'{self} | No review jobs for "{task_name}" task')
            return
        hp_reviews = []
        reviews = []
        answers = []
        for question in data:
            honey_pot_data = question['honeyPotData']
            if honey_pot_data:
                honey_pot_session: dict = honey_pot_data['hpReviewSession']
                question_type = honey_pot_data['question']['questionType']
                if question_type == 'text':
                    hp_reviews.append(dict(
                        reviewResult=honey_pot_data['question']['answerCorrect'],
                        hpReviewSessionId=honey_pot_session['id'],
                        honeyPotReviewSession=honey_pot_session,
                    ))
                elif question_type == 'single_choice':
                    details = json.loads(honey_pot_data['question']['details'])
                    options = details['options']
                    answer_index = int(honey_pot_data['question']['answer'])
                    question_string = honey_pot_data['question']['question']
                    answer, index = await self._get_answer_to_question_index_gpt(
                        SingleChoiceQuestion(question=question_string, options=options)
                    )
                    hp_reviews.append(dict(
                        reviewResult=index == answer_index,
                        hpReviewSessionId=honey_pot_session['id'],
                        honeyPotReviewSession=honey_pot_session,
                    ))
                else:
                    return
            try:
                answers.append([answer for answer in json.loads(question['taskSession']['answer'])])
            except JSONDecodeError as e:
                answers.append(None)
            reviews.append(dict(
                approve=True,
                jobId=question['taskSession']['jobId'],
                reviewSessionId=question['reviewSession']['id'],
                taskSessionId=question['taskSession']['id'],
            ))
        return hp_reviews, answers, reviews

    async def get_annotating_answers(self, job_id: int, task_name: str) -> tuple[list, list, list, list] | bool | None:
        try:
            _, data = await self.session.get(f'{self.API_URL}/jobs/{job_id}/take-job/for-individuals')
        except RequestsError as e:
            if 'User workloads exceeded' in str(e):
                logger.debug(f'{self} | Limit reached for "{task_name}" (Labeler) task')
            return False
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        if not (data := data.get('data')):
            logger.info(f'{self} | No annotating jobs for "{task_name}" task')
            return
        submit_hp_answers = []
        submit_answers = []
        hp_data = []
        task_descriptions = []
        for question in data:
            honey_pot_data = question['honeyPotData']
            honey_pot_question = honey_pot_data['question']['question']
            honey_pot_options = json.loads(honey_pot_data['question']['details'])['options']
            honey_pot_session = honey_pot_data['honeyPotSession']
            task_session = question['taskSession']
            submit_hp_answers.append(dict(honeyPotSession=honey_pot_session, taskSessionId=task_session['id']))
            submit_answers.append(dict(
                taskSession=task_session, taskSessionId=task_session['id'], submitAnswer=dict(feedback='')
            ))
            hp_data.append({'question': honey_pot_question, 'options': honey_pot_options})
            task_descriptions.append(question['resource']['data'])
        return submit_hp_answers, submit_answers, hp_data, task_descriptions

    async def submit_review(self, hp_reviews: list[dict], reviews: list[dict], task_name: str, job_id: int):
        payload = dict(captchaToken="", hpReviews=hp_reviews, reviews=reviews)
        for i in range(retry_count):
            try:
                _, data = await self.session.post(f'{self.API_URL}/review-sessions/submit-revisions', json=payload)
                break
            except RequestsError as e:
                logger.warning(f'{self} | {e}')
                payload['captchaToken'] = await self._solve_captcha(
                    f'https://app.saharalabs.ai/#/individualLabeler/working/{job_id}'
                )
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        logger.success(f'{self} | Submitted {len(reviews)} datapoints for reviewing "{task_name}" task')

    async def submit_annotating(self, answers: list[dict], hp_answers: list[dict], task_name: str, job_id: int):
        payload = dict(captchaToken=await self._solve_captcha(
            f'https://app.saharalabs.ai/#/individualLabeler/working/{job_id}'
        ), submitAnswers=answers, submitHPAnswers=hp_answers)
        logger.info(payload)
        try:
            _, data = await self.session.post(f'{self.API_URL}/task-sessions/submit-answers', json=payload)
        except RequestsError as e:
            logger.error(f'{self} | {e}')
            return
        if not data['success']:
            logger.error(f'{self} | Something went wrong: {data}')
            return
        logger.success(f'{self} | Submitted {len(answers)} datapoints for annotating "{task_name}" task')


async def check_wl():
    def get_accounts_from_privates():
        with open(data_path / 'sahara/privates.txt', encoding='utf-8') as file:
            privates = [row.strip() for row in file.readlines()]
        return [SaharaAccount(private=private, proxy=Web3mtENV.ROTATING_PROXY) for private in privates]

    MAX_PARALLEL_TASKS = 8
    semaphore = Semaphore(MAX_PARALLEL_TASKS)

    async def wait_flag(account: SaharaAccount, save_session=False):
        async with semaphore:
            async with SaharaClient(account, save_session=save_session) as client:
                if not client.user_info['waitFlag']:
                    logger.success(f'{client} | Found')

    accounts = get_accounts_from_privates()
    # accounts = await db_helper.get_all_from_table(SaharaAccount)
    await asyncio.gather(*[wait_flag(acc, save_session=False) for acc in accounts])


async def points(account: SaharaAccount):
    async with SaharaClient(account) as client:
        return client.sp


async def points_checker(ids: list[int] = None):
    if not ids:
        accounts = await db_helper.get_all_from_table(SaharaAccount)
    else:
        accounts = await db_helper.get_rows_by_filter(ids, SaharaAccount, SaharaAccount.account_id)
    total = await asyncio.gather(*[points(account) for account in accounts])
    logger.success(f'Total: {sum(total)} SP')


# semaphore = Semaphore(8)


async def start(account: SaharaAccount, more_than_one_accounts: bool):
    # async with semaphore:
        if more_than_one_accounts:
            await sleep(0, 600, log_info=f'{account}', echo=True)
        async with SaharaClient(account) as client:
            if not client:
                return
            await client.do_tasks()
            return client.sp
            # await client.claim_in_progress_achievements()
            # await client.mint_in_progress_achievements()


async def main():
    accounts = await db_helper.get_rows_by_filter(a_1 + a_2 + a_3, SaharaAccount, SaharaAccount.account_id)
    # accounts: list[SaharaAccount] = await db_helper.get_all_from_table(SaharaAccount)
    random.shuffle(accounts)
    await asyncio.gather(*[start(acc, len(accounts) > 1) for acc in accounts])


if __name__ == '__main__':
    a_1 = [226, 227, 229, 262, 263, 265, 266, 268, 269, 274, 277]
    a_2 = [1, 42, 43, 53, 54, 55, 56]
    a_3 = [1111, 111, 115, 142, 144, 192, 197, 201, 203, 221, 225]
    # asyncio.run(points_checker(a_1 + a_2 + a_3))
    asyncio.run(main())
