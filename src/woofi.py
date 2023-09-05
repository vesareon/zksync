import time
import json
import random
from web3 import Web3
from loguru import logger as logging

from src.account import Account
from src.utils import check_allowance, value_for_logs
from config import TOKENS, WOOFI_ROUTER_ADDRESS, GAS_THRESHOLD


class WooFi:
    def __init__(self, account: Account, slippage: float = 0.5, retries: int = 2):
        self.w3 = account.w3
        self.account = account
        self.retries = retries
        self.slippage = slippage
        self.router_address = Web3.to_checksum_address(WOOFI_ROUTER_ADDRESS)
        self.router = self.w3.eth.contract(self.router_address, abi=json.load(open('ABIs/woofi_router.json')))

    def swap(self, from_token: str, to_token: str, amount: int, retry: int = 0) -> bool:
        eth = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        address = Web3.to_checksum_address(self.account.address)
        from_token_address = Web3.to_checksum_address(TOKENS[from_token] if from_token != 'eth' else eth)
        to_token_address = Web3.to_checksum_address(TOKENS[to_token] if to_token != 'eth' else eth)

        try:
            if from_token != 'eth':
                token = self.w3.eth.contract(address=from_token_address, abi=json.load(open('ABIs/erc20_abi.json')))
                check_allowance(self.w3, token, address, self.router_address, amount, self.account.key)

            amount_out = self.router.functions.tryQuerySwap(from_token_address, to_token_address, amount).call()

            swap_txn = self.router.functions.swap(
                from_token_address,
                to_token_address,
                amount,
                int(amount_out - (amount_out * self.slippage // 1000)),
                address,
                address
            ).build_transaction({
                'from': address,
                'value': amount if from_token == 'eth' else 0,
                'nonce': self.w3.eth.get_transaction_count(address),
                'gas': 0,
                'maxFeePerGas': self.w3.eth.gas_price,
                'maxPriorityFeePerGas': self.w3.eth.gas_price
            })

            swap_txn['gas'] = random.randint(890000, 1000000) if GAS_THRESHOLD < 21 else self.w3.eth.estimate_gas(txn)
            signed_swap_txn = self.w3.eth.account.sign_transaction(swap_txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | WOOFi swap: {value_for_logs(from_token, amount)} -> '
                                f'{value_for_logs(to_token, amount_out)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | WOOFi swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                              f' -> {to_token}')
                if retry < self.retries:
                    time.sleep(random.randint(35, 60))
                    self.swap(from_token, to_token, amount, retry + 1)
                else:
                    return False

        except Exception as err:
            logging.error(f'{address} | WOOFi swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                          f' -> {to_token} | {err}')
            if retry < self.retries:
                time.sleep(random.randint(35, 60))
                self.swap(from_token, to_token, amount, retry + 1)
            else:
                return False
