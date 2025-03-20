import asyncio
import json
import sys
import aiofiles
from eth_keys.datatypes import Signature
from eth_utils import keccak, decode_hex, encode_hex
from g4f import AsyncClient
from g4f.Provider import DDG, Free2GPT, GizAI
from g4f.providers.retry_provider import RetryProvider
from pathlib import Path

from web3mt.consts import Web3mtENV
from web3mt.onchain.evm.models import Chain
from web3mt.utils import FileManager, my_logger as logger
from web3mt.utils.db import create_db_instance


def recover_public_key(message: str, signature: str) -> str:
    prefix = f"\x19Ethereum Signed Message:\n{len(message)}".encode()
    digest = keccak(prefix + message.encode('utf-8'))
    signature = decode_hex(signature)
    r = int.from_bytes(signature[:32], byteorder='big')
    s = int.from_bytes(signature[32:64], byteorder='big')
    v = signature[64]
    if v >= 27:
        v -= 27
    signature_obj = Signature(vrs=(v, r, s))
    public_key = signature_obj.recover_public_key_from_msg_hash(digest)
    return '0x04' + encode_hex(public_key.to_bytes())[2:]


SaharaAI_Testnet = Chain(
    name='SaharaAI Testnet',
    rpc='https://testnet.saharalabs.ai',
    chain_id=313313,
    explorer='https://testnet-explorer.saharalabs.ai',
)
SaharaAI_Testnet.native_token.symbol = 'SAHARA'

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

data_path = ROOT_DIR / 'data'
abi = FileManager.read_json(data_path / 'abi.json')
contract_address = '0x0a05D8C72Bb1991E526b0357491043FaDeb40EF9'
CONNECTION_STRING = f'sqlite+aiosqlite:///{data_path}/sahara.db'
db_helper = create_db_instance(CONNECTION_STRING)

answers_storage = json.load(open(data_path / 'answers_storage.json'))
gpt_client = AsyncClient(provider=RetryProvider([DDG, Free2GPT, GizAI], shuffle=True))
exam_system_messages = [{
    "role": "system",
    "content": (
        "You are an AI assistant designed to answer multiple-choice test questions. "
        "Always select the best answer from the provided options without generating additional responses. "
        "Write only full string of selected option"
    )
}]
review_system_messages = [{
    "role": "system",
    "content": (
        "You are an AI assistant created to check answers to questions. "
        "You will be provided with questions and answers to them. "
        "You only need to determine whether the answer is appropriate in meaning and related to the given topic. "
        'Answers must be "true" or "false". Write answer to each set of questions and answers. '
        "Write your answer as plain text in one line with commas separating each answer"
    )
}]
annotate_system_messages = [{
    "role": "system",
    "content": (
        "You are an AI assistant created to annotate text. You will be given a tasks with a description of it. "
        "You will also be given questions that you need to answer in as much detail as possible. "
        "You need to answer in a non-standard, very unique way. Cut out typical, popular answers. Think carefully. "
        "Answer like a real person. The most important thing is not to repeat previous answers. "
        "Separate the answers to the questions with a blank line between them. "
        "WRITE ONLY ANSWERS with nothing more and don't repeat questions in answers"
    )
}]
offset = 5


async def update_exam_storage():
    async with aiofiles.open(data_path / 'answers_storage.json', 'w', encoding='utf-8') as f:
        await f.write(json.dumps(answers_storage))


def count_set_bits(number):
    return bin(number).count('1')


def parse_requirement_bitmap(requirement_bitmap: int, onchain_requirement_bitmap: int = 0, total_days: int = 31):
    completed_days = [day + 1 for day in range(total_days) if (requirement_bitmap >> day) & 1]
    claimable_days = [day for day in completed_days if not ((onchain_requirement_bitmap >> (day - 1)) & 1)]
    claimable_requirement_no = claimable_days
    return claimable_requirement_no


class Conversation:
    def __init__(self, task_description: str, first_content: str, offset: int = 0):
        self.client = AsyncClient()
        system = f'{annotate_system_messages[0]["content"]}.\nTask: {task_description}'
        self.history = [{'role': 'system', 'content': system}, {'role': 'system', 'content': first_content}]
        self.history_set_count = len(self.history)
        self.offset = offset
        self.initialized = False

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})

    async def _make_request(self):
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.history,
            web_search=False,
            proxy=Web3mtENV.ROTATING_PROXY
        )
        assistant_response = response.choices[0].message.content
        logger.info(
            f'Response №{len(self.history) - self.history_set_count + 1}, provider - {response.provider}:\n'
            f'{assistant_response}'
        )
        self.history.append({"role": "assistant", "content": assistant_response})
        return assistant_response

    async def _generate_initial_messages(self):
        if self.offset > 0 and not self.initialized:
            for i in range(self.offset):
                await self._make_request()
            self.initialized = True

    async def get_response(self, user_message: str = None):
        if not self.initialized:
            await self._generate_initial_messages()
        if user_message:
            self.add_message("user", user_message)
        return await self._make_request()


async def test_gpt_annotate():
    task_description = "Understanding future technology trends can help individuals and businesses stay ahead of the competition and prepare for upcoming innovations.\n\n**Task:** Predict future trends in technology.\n\n* **Prediction:** Describe the upcoming trend.Example: \"Artificial General Intelligence (AGI) will become a reality within the next decade.\"\n* **Basis:** What data supports this prediction?Example: \"Recent advancements in deep learning and neural networks show exponential progress.\"\n* **Impact Potential:** How could it shape the industry?Example: \"AGI could revolutionize industries by automating complex decision-making processes.\""
    questions = [
        {
            "question": "Describe the upcoming trend.",
            "details": "{\"questionType\":\"text\",\"conditions\":[],\"text\":\"\",\"minLength\":10,\"maxLength\":600,\"placeholder\":\"\",\"grammarIssues\":{},\"enableMachineReview\":true,\"enablePipelineCheck\":false,\"needReviewers\":true}",
        },
        {
            "question": "What data supports this prediction?",
            "details": "{\"questionType\":\"text\",\"conditions\":[],\"text\":\"\",\"minLength\":10,\"maxLength\":600,\"placeholder\":\"\",\"grammarIssues\":{},\"enableMachineReview\":true,\"enablePipelineCheck\":false,\"needReviewers\":true}",
        },
        {
            "question": "How could it shape the industry?",
            "details": "{\"questionType\":\"text\",\"conditions\":[],\"text\":\"\",\"minLength\":10,\"maxLength\":600,\"placeholder\":\"\",\"grammarIssues\":{},\"enableMachineReview\":true,\"enablePipelineCheck\":false,\"needReviewers\":true}",
        }
    ]
    content = ''
    for question in questions:
        details = json.loads(question['details'])
        min_length = details['minLength']
        max_length = details['maxLength']
        content += f'{question["question"]}. Answer in {min_length}-{max_length} characters\n'
    conversation = Conversation(task_description, content, 5)
    for i in range(50):
        response = await conversation.get_response()
        if len(response.split('\n\n')) != len(questions):
            conversation = Conversation(task_description, content, 5)


if __name__ == '__main__':
    asyncio.run(test_gpt_annotate())
    # test_openai()
