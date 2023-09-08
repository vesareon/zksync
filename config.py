# Прокси для Odos, формат: ip:port:login:password
PROXY = ""

# Минимальный баланс в ETH, оставляемый на газ, при прогоне ОБЪМОВ: [min, max]
MIN_BALANCE_FOR_GAS = [0.0007, 0.0012]

# Процент используемого баланса при обычном прогреве: [min, max]
BALANCE_PERCENTAGE = [0.5, 0.6]  # 0.3 == 30%

# Максимальное кол-во непрерывных транзакций в одном DEX
MAX_CONTINUOUS_TRANS = 5

# Количество депозитов в пулы: [min, max]
SYNCSWAP_DEPOSIT = [0, 1]
SPACEFI_DEPOSIT = [0, 1]

# Сумма в ETH, которая будет добавлена в пулы: [min, max]
LIQUIDITY_AMOUNT = [0.00005, 0.0001]

# Сумма депозита из Ethereum Mainnet в zkSync Era: [min, max]
BRIDGE_AMOUNT = [0.01, 0.015]  # в eth

# Использовать офф мост при наличии ETH в zkSync Era: True (да) или False (нет)
BRIDGE = True

# Ограничение по стоимости газа в GWEI (Код написан под GAS_THRESHOLD <= 20, увеличение может привести к ошибкам)
GAS_THRESHOLD = 20

# Время ожидание между транзакциями в секундах: [min, max]
SLEEP_TRANSACTIONS = [25, 45]

# Время ожидание между кошельками в секундах: [min, max]
SLEEP_WALLETS = [60, 180]

RPC = "https://rpc.ankr.com/zksync_era"
SCAN = "https://explorer.zksync.io"
ETHEREUM_RPC = "https://eth.llamarpc.com"

TOKENS = {
    "eth": "0x5AEa5775959fBC2557Cc8789bC1bf90A239D9a91",
    "usdc": "0x3355df6D4c9C3035724Fd0e3914dE96A5a83aaf4",
    "usdt": "0x493257fD37EDB34451f62EDf8D2a0C418852bA4C",
    "busd": "0x2039bb4116B4EFc145Ec4f0e2eA75012D6C0f181",
    "zero_address": "0x0000000000000000000000000000000000000000"
}

OFFICIAL_BRIDGE = "0x32400084C286CF3E17e7B677ea9583e60a000324"
ODOS_ROUTER_ADDRESS = "0x4bBa932E9792A2b917D47830C93a9BC79320E4f7"
INCH_ROUTER_ADDRESS = "0x6e2B76966cbD9cF4cC2Fa0D76d24d5241E0ABC2F"
WOOFI_ROUTER_ADDRESS = "0xfd505702b37Ae9b626952Eb2DD736d9045876417"
SPACEFI_ROUTER_ADDRESS = "0xbE7D1FD1f6748bbDefC4fbaCafBb11C6Fc506d1d"
SYNCSWAP_ROUTER_ADDRESS = "0x2da10A1e27bF85cEdD8FFb1AbBe97e53391C0295"
SYNCSWAP_STABLE_POOL_FACTORY_ADDRESS = "0x5b9f21d407F35b10CbfDDca17D5D84b129356ea3"
SYNCSWAP_CLASSIC_POOL_FACTORY_ADDRESS = "0xf2DAd89f2788a8CD54625C60b55cD3d2D0ACa7Cb"
