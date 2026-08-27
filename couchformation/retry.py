##
##

import logging
from typing import Callable, Optional, Tuple, Type, Union

from tenacity import (
    retry as tenacity_retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryCallState,
)

logger = logging.getLogger('couchformation.retry')
logger.addHandler(logging.NullHandler())

ExceptionTypes = Union[Type[BaseException], Tuple[Type[BaseException], ...]]


def _before_sleep(retry_state: RetryCallState) -> None:
    fn_name = retry_state.fn.__name__ if retry_state.fn else "callable"
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.debug(f"{fn_name} will retry, number {attempt}: {exc}")


def retry_inline(func, *args, retry_count=10, factor=0.01, **kwargs):
    @tenacity_retry(
        reraise=True,
        stop=stop_after_attempt(retry_count + 1),
        wait=wait_exponential(multiplier=factor, exp_base=2),
        before_sleep=_before_sleep,
    )
    def _wrapped():
        return func(*args, **kwargs)

    return _wrapped()


def retry(
    retry_count: int = 10,
    factor: float = 0.01,
    allow_list: Optional[ExceptionTypes] = None,
    always_raise_list: Optional[ExceptionTypes] = None,
) -> Callable:
    retry_condition = None
    if allow_list is not None:
        retry_condition = retry_if_exception_type(allow_list)

    def retry_handler(func):
        kwargs = {
            "reraise": True,
            "stop": stop_after_attempt(retry_count + 1),
            "wait": wait_exponential(multiplier=factor, exp_base=2),
            "before_sleep": _before_sleep,
        }
        if retry_condition is not None:
            kwargs["retry"] = retry_condition

        wrapped = tenacity_retry(**kwargs)(func)

        if always_raise_list is None:
            return wrapped

        def guarded(*args, **inner_kwargs):
            try:
                return wrapped(*args, **inner_kwargs)
            except always_raise_list:
                raise

        return guarded

    return retry_handler
