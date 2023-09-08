import time
import json
import random
from web3 import Web3
from eth_abi import encode
from loguru import logger as logging


from src.account import Account
from src.utils import check_allowance, value_for_logs
from config import TOKENS, LIQUIDITY_AMOUNT, SYNCSWAP_ROUTER_ADDRESS, GAS_THRESHOLD
from config import SYNCSWAP_CLASSIC_POOL_FACTORY_ADDRESS, SYNCSWAP_STABLE_POOL_FACTORY_ADDRESS


class SyncSwap:
    def __init__(self, account: Account, slippage: float = 0.5, retries: int = 1) -> None:
        self.w3 = account.w3
        self.account = account
        self.retries = retries
        self.slippage = slippage
        self.router_address = Web3.to_checksum_address(SYNCSWAP_ROUTER_ADDRESS)
        self.classic_pool_factory_address = Web3.to_checksum_address(SYNCSWAP_CLASSIC_POOL_FACTORY_ADDRESS)
        self.stable_pool_factory_address = Web3.to_checksum_address(SYNCSWAP_STABLE_POOL_FACTORY_ADDRESS)

    def swap(self, from_token: str, to_token: str, amount: int, retry: int = 0) -> bool:
        address = Web3.to_checksum_address(self.account.address)
        from_token_address = Web3.to_checksum_address(TOKENS[from_token])

        try:
            if from_token != 'eth':
                token = self.w3.eth.contract(address=from_token_address, abi=json.load(open('ABIs/erc20_abi.json')))
                check_allowance(self.w3, token, address, self.router_address, amount, self.account.key)

            pool_address = self.get_pool_address(from_token, to_token)

            if pool_address == TOKENS['zero_address']:
                logging.error(f"{address} | SyncSwap | Pool not exists")
                return False

            swap_data = encode(
                ["address", "address", "uint8"],
                [from_token_address, address, 1]
            )

            steps = [{
                "pool": pool_address,
                "data": swap_data,
                "callback": TOKENS['zero_address'],
                "callbackData": "0x",
            }]

            paths = [{
                "steps": steps,
                "tokenIn": from_token_address if from_token != 'eth' else TOKENS['zero_address'],
                "amountIn": amount,
            }]

            router = self.w3.eth.contract(self.router_address, abi=json.load(open('ABIs/syncswap_router.json')))
            amount_out = self.get_amount_out(pool_address, from_token_address, amount)

            swap_txn = router.functions.swap(
                paths,
                int(amount_out - (amount_out * self.slippage // 1000)),
                int(time.time() + 1800)
            ).build_transaction({
                'from': address,
                'value': amount if from_token.lower() == 'eth' else 0,
                'nonce': self.w3.eth.get_transaction_count(address),
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price
            })

            swap_txn['gas'] = random.randint(870000, 950000) if GAS_THRESHOLD < 21 else self.w3.eth.estimate_gas(swap_txn)
            signed_swap_txn = self.w3.eth.account.sign_transaction(swap_txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | SyncSwap swap: {value_for_logs(from_token, amount)} -> '
                                f'{value_for_logs(to_token, amount_out)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | SyncSwap swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                              f' -> {to_token}')
                if retry < self.retries:
                    time.sleep(random.randint(35, 60))
                    self.swap(from_token, to_token, amount, retry + 1)
                else:
                    return False

        except Exception as err:
            logging.error(f'{address} | SyncSwap swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                          f' -> {to_token} | {err}')
            if retry < self.retries:
                time.sleep(random.randint(35, 60))
                self.swap(from_token, to_token, amount, retry + 1)
            else:
                return False

    def add_liquidity(self, from_token: str = 'usdc', to_token: str = 'eth') -> bool:
        address = Web3.to_checksum_address(self.account.address)
        pool_address = self.get_pool_address(from_token, to_token)

        router = self.w3.eth.contract(self.router_address, abi=json.load(open('ABIs/syncswap_router.json')))

        amount = int(random.uniform(*LIQUIDITY_AMOUNT) * 10 ** 18)

        if amount > self.account.get_native_balance():
            return False

        try:
            txn = router.functions.addLiquidity2(
                pool_address,
                [
                    [Web3.to_checksum_address(TOKENS['usdc']), 0],
                    [Web3.to_checksum_address(TOKENS['zero_address']), amount]
                ],
                encode(["address"], [address]),
                0,
                TOKENS['zero_address'],
                "0x"
            ).build_transaction({
                'from': address,
                'value': amount,
                'nonce': self.w3.eth.get_transaction_count(address),
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price
            })

            txn['gas'] = self.w3.eth.estimate_gas(txn)
            signed_swap_txn = self.w3.eth.account.sign_transaction(txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | SyncSwap add liquidity: {from_token} & {to_token} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | SyncSwap add liquidity {from_token} & {to_token}')
                return False
        except Exception as err:
            logging.error(f'{address} | SyncSwap add liquidity error: {err}')

    def get_pool_address(self, from_token: str, to_token: str):
        stables = ['usdc', 'usdt', 'busd']
        if from_token in stables and to_token in stables:
            pool_factory_address = self.stable_pool_factory_address
        else:
            pool_factory_address = self.classic_pool_factory_address

        classic_pool_factory = self.w3.eth.contract(
            pool_factory_address,
            abi=json.load(open('ABIs/syncswap_classic_pool.json'))
        )
        pool_address = classic_pool_factory.functions.getPool(
            Web3.to_checksum_address(TOKENS[from_token]),
            Web3.to_checksum_address(TOKENS[to_token])
        ).call()

        return pool_address

    def get_amount_out(self, pool_address: str, from_token_address: str, amount: int):
        pool = self.w3.eth.contract(
            Web3.to_checksum_address(pool_address),
            abi=json.load(open('ABIs/syncswap_pool_data.json'))
        )

        amount_out = pool.functions.getAmountOut(
            from_token_address,
            amount,
            Web3.to_checksum_address(self.account.address)
        ).call()
        return amount_out
