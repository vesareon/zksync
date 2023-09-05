import time
import json
import random
from web3 import Web3
from loguru import logger as logging


from src.account import Account
from src.utils import check_allowance, value_for_logs
from config import TOKENS, SPACEFI_ROUTER_ADDRESS, LIQUIDITY_AMOUNT, GAS_THRESHOLD


class SpaceFi:
    def __init__(self, account: Account, retries: int = 2):
        self.w3 = account.w3
        self.retries = retries
        self.account = account
        self.router_address = Web3.to_checksum_address(SPACEFI_ROUTER_ADDRESS)
        self.router = self.w3.eth.contract(self.router_address, abi=json.load(open('ABIs/spacefi_router.json')))

    def swap(self, from_token: str, to_token: str, amount: int, retry: int = 0) -> bool:
        address = Web3.to_checksum_address(self.account.address)
        from_token_address = Web3.to_checksum_address(TOKENS[from_token])
        to_token_address = Web3.to_checksum_address(TOKENS[to_token])

        deadline = int(time.time() + 1800)

        try:
            if from_token == 'eth':
                amount_out = self.get_amount_out(from_token, to_token, amount)[-1]

                swap_txn = self.router.functions.swapExactETHForTokens(
                    amount_out,
                    [from_token_address, to_token_address],
                    address,
                    deadline
                ).build_transaction({
                    'from': address,
                    'value': amount if from_token.lower() == 'eth' else 0,
                    'nonce': self.w3.eth.get_transaction_count(address),
                    'gas': 0,
                    'maxFeePerGas': self.w3.eth.gas_price,
                    'maxPriorityFeePerGas': self.w3.eth.gas_price,
                })
            else:
                token = self.w3.eth.contract(address=from_token_address, abi=json.load(open('ABIs/erc20_abi.json')))
                amount_out = self.get_amount_out(from_token, to_token, amount)[-1]

                check_allowance(self.w3, token, address, self.router_address, amount, self.account.key)

                txn_info = {
                    'from': address,
                    'value': amount if from_token.lower() == 'eth' else 0,
                    'nonce': self.w3.eth.get_transaction_count(address),
                    'gas': 0,
                    'maxFeePerGas': self.w3.eth.gas_price,
                    'maxPriorityFeePerGas': self.w3.eth.gas_price,
                }
                params = [amount, amount_out, [from_token_address, to_token_address], address, deadline]

                if to_token == 'eth':
                    swap_txn = self.router.functions.swapExactTokensForETH(*params).build_transaction(txn_info)
                else:
                    swap_txn = self.router.functions.swapExactTokensForTokens(*params).build_transaction(txn_info)

            swap_txn['gas'] = random.randint(890000, 1000000) if GAS_THRESHOLD < 21 else self.w3.eth.estimate_gas(txn)
            signed_swap_txn = self.w3.eth.account.sign_transaction(swap_txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | SpaceFi swap: {value_for_logs(from_token, amount)} -> '
                                f'{value_for_logs(to_token, amount_out)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | SpaceFi swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                              f' -> {to_token}')
                if retry < self.retries:
                    time.sleep(random.randint(35, 60))
                    self.swap(from_token, to_token, amount, retry + 1)
                else:
                    return False

        except Exception as err:
            logging.error(f'{address} | SpaceFi swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                          f' -> {to_token} | {err}')
            if retry < self.retries:
                time.sleep(random.randint(35, 60))
                self.swap(from_token, to_token, amount, retry + 1)
            else:
                return False

    def add_liquidity(self, to_token: str) -> bool:
        address = Web3.to_checksum_address(self.account.address)
        amount = int(random.uniform(*LIQUIDITY_AMOUNT) * 10 ** 18)
        token_balance = self.account.get_token_data(TOKENS[to_token])['balance_wei']

        try:
            token_amount = self.get_amount_out('eth', to_token, amount)[-1]
            
            if amount > self.account.get_native_balance() or token_amount > token_balance:
                return False

            txn = self.router.functions.addLiquidityETH(
                Web3.to_checksum_address(TOKENS[to_token]),
                token_amount,
                int(token_amount * 0.995),
                int(amount * 0.995),
                address,
                int(time.time() + 1800)
            ).build_transaction({
                    'from': address,
                    'value': amount,
                    'nonce': self.w3.eth.get_transaction_count(address),
                    'gas': 0,
                    'maxFeePerGas': self.w3.eth.gas_price,
                    'maxPriorityFeePerGas': self.w3.eth.gas_price,
            })

            txn['gas'] = self.w3.eth.estimate_gas(txn)
            signed_swap_txn = self.w3.eth.account.sign_transaction(txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | SpaceFi add liquidity: eth & {to_token}: {value_for_logs(to_token, token_amount)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | SpaceFi add liquidity')
                return False
        except Exception as err:
            logging.error(f'{address} | SpaceFi add liquidity error: {err}')

    def get_amount_out(self, from_token: str, to_token: str, amount: int):
        amount_out = self.router.functions.getAmountsOut(
            amount,
            [
                Web3.to_checksum_address(TOKENS[from_token]),
                Web3.to_checksum_address(TOKENS[to_token])
            ]
        ).call()

        return amount_out

