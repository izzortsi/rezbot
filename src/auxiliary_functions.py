import pandas as pd
import datetime


def name_trader(strategy, symbol):
    return "_".join([strategy.name, symbol, strategy.timeframe])


def to_percentual(exit_price, entry_price, leverage=1):
    """
    Converts a difference in values to a percentual difference.

    Args:
        exit_price (float or integer)
        entry_price (float or integer)
        leverage (int)
    Returns:
        float: ((exit_price - entry_price) / entry_price) * 100 * leverage
    """
    return ((exit_price - entry_price) / entry_price) * 100 * leverage


def to_datetime_tz(arg, timedelta=-pd.Timedelta("03:00:00"), unit="s", **kwargs):
    """
    to_datetime_tz(arg, timedelta=-pd.Timedelta("03:00:00"), unit="s", **kwargs)

    Args:
        arg (float): epochtime
        timedelta (pd.Timedelta): timezone correction
        unit (string): unit in which `arg` is
        **kwargs: pd.to_datetime remaining kwargs
    Returns:
    pd.Timestamp: a timestamp corrected by the given timedelta
    """
    ts = pd.to_datetime(arg, unit=unit)
    return ts + timedelta


def strf_epoch(epochtime, fmt="%j-%y_%H-%M-%S"):
    """
    returns: string
    """

    """
    epochtime to string using datetime
    signature: def strf_epoch(epochtime, fmt="%j-%y_%H-%M-%S")

    Args:
        epochtime (float): epochtime as float in seconds
        fmt (string): format for the timestamp string
    Returns:
        string: stringfied epochtime: datetime.fromtimestamp(epochtime).strftime(fmt)
    """

    return datetime.fromtimestamp(epochtime).strftime(fmt)


def f_tp_price(price, tp, lev, precision=3, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(tp/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(tp/lev)/100)):.2f}"


def f_sl_price(price, sl, lev, precision=3, side="BUY"):
    if side == "BUY":
        return f"{(price * (1+(sl/lev)/100)):.2f}"
    elif side == "SELL":
        return f"{(price * (1-(sl/lev)/100)):.2f}"  # sl is supposed negative


def rows_to_csv(rows: list, num_rows: int, path: str):
    for i, row in enumerate(rows[-num_rows:]):
        if i == 0:
            row.to_csv(path, header=True, mode="w", index=False)
        elif i > 0:
            row.to_csv(path, header=False, mode="a", index=False)


substring_check = np.frompyfunc((lambda s, array: s in array), 2, 1)
