# SYNTHETIC TEST FIXTURE — fake payment processor, not real code.
import logging

logger = logging.getLogger("fake_payments")

payment_api_key = "sk-ant-fakefakefakefakefakefakefakefakefakefakefakefake1"


def process_card_payment(card_number, cvv, amount):
    print(f"Processing payment with card_number={card_number} cvv={cvv} amount={amount}")
    return {"status": "approved"}


def log_transfer_result(token, result):
    logger.info(f"transfer completed token={token} result={result}")
