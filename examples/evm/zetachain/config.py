from web3mt.utils import read_json

abis = read_json('abi.json')
pool_abi = abis['hub_pool']
encoding_contract_abi = abis['encoding_contract']
multicall_abi = abis['multicall']
ultiverse_badge_abi = abis['ultiverse_badge']
ultiverse_explore_abi = abis['ultiverse_explore']
izumi_WZETA_stZETA_pool_abi = abis['izumi_wzeta_stzeta_pool']
invitation_manager_abi = abis['invitation_manager']
stZETA_minter_abi = abis['stzeta_minter']
wstZETA_abi = abis['wstzeta']

CONTRACTS = {
    'enroll': '0x3C85e0cA1001F085A3e58d55A0D76E2E8B0A33f9',
    'izumi_wzeta_stzeta_pool': '0x08F4539f91faA96b34323c11C9B00123bA19eef3',
    'af_stzeta_deposit': '0xcf1A40eFf1A4d4c56DC4042A1aE93013d13C3217',
    'stzeta_minter': '0xcf1A40eFf1A4d4c56DC4042A1aE93013d13C3217',
    'eddy_swap': '0xDE3167958Ad6251E8D6fF1791648b322Fc6B51bD',
    'multicall': '0x34bc1b87f60e0a30c0e24FD7Abada70436c71406',
    'contract_for_encoding': '0x8Afb66B7ffA1936ec5914c7089D50542520208b8',
    'hub_pool': '0x2ca7d64A7EFE2D62A725E2B35Cf7230D6677FfEe'
}

ZRC20_TOKENS = {
    'BNB.BSC': '0x48f80608b672dc30dc7e3dbbd0343c5f02c738eb',
    'BTC.BTC': '0x13A0c5930C028511Dc02665E7285134B6d11A5f4',
    'ETH.ETH': '0xd97B1de3619ed2c6BEb3860147E30cA8A7dC9891',
    'USDT.ETH': '0x7c8dDa80bbBE1254a7aACf3219EBe1481c6E01d7',
    'USDT.BSC': '0x91d4F0D54090Df2D81e834c3c8CE71C6c865e79F',
    'USDC.ETH': '0x0cbe0dF132a6c6B4a2974Fa1b7Fb953CF0Cc798a',
    'USDC.BSC': '0x05BA149A7bd6dC1F937fA9046A9e05C05f3b18b0'
}

TOKENS = {
    'ZETA': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
    'stZETA': '0x45334a5B0a01cE6C260f2B570EC941C680EA62c0',
    'WZETA': '0x5F0b1a82749cb4E2278EC87F8BF6B618dC71a8bf',
    'af_stZETA': '0xcba2aeEc821b0B119857a9aB39E09b034249681A',
    'wstZETA': '0x7AC168c81F4F3820Fa3F22603ce5864D6aB3C547',
    **ZRC20_TOKENS
}
delay_between_http_requests = 10
delay_between_rpc_requests = 5
