from vnpy.trader.constant import Interval, Direction, Offset
from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class TurtleStrategy(CtaTemplate):
    author = "yzs"

    donchian_channel_open_position=20
    donchian_channel_stop_profit=10
    atr_day_length=20
    max_risk_ratio=0.5
    risk_factor = 0.02
    balance = 350000
    max_add_pos = 2  # 最大建仓次数

    parameters = [
        "donchian_channel_open_position",
        "donchian_channel_stop_profit",
        "atr_day_length",
        "max_risk_ratio",
        "risk_factor",
        "balance",
        "max_add_pos",
    ]

    n = 0.0  # atr
    unit = 0  # 买卖单位
    donchian_channel_high = 0.0  # 唐奇安通道上轨
    donchian_channel_low = 0.0  # 唐奇安通道下轨
    short_donchian_channel_high = 0.0  # 用于止盈的唐奇安通道上轨
    short_donchian_channel_low = 0.0  # 用于止盈的唐奇安通道下轨
    last_price = 0.0  # 上次调仓价格
    high_price = 0.0  # 开仓后的最高价
    low_price = 1e9  # 开仓后的最低价
    add_pos = 0  # 建仓次数
    multiplier = 0

    variables = [
        "n",
        "unit",
        "donchian_channel_high",
        "donchian_channel_low",
        "short_donchian_channel_high",
        "short_donchian_channel_low",
        "last_price",
        "high_price",
        "low_price",
        "add_pos",
        "multiplier",
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar)
        self.kline_length = max(self.donchian_channel_open_position + 1,
                           self.donchian_channel_stop_profit + 1,
                           self.atr_day_length + 1)
        self.am = ArrayManager(self.kline_length)
        # self.multiplier = self.get_size()
        # self.multiplier = 10

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(self.kline_length * 3, interval=Interval.DAILY, callback=self.on_bar)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.multiplier = self.get_size()
        self.update_param()
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        # self.bg.update_tick(tick)
        if not self.am.inited or not self.trading:
            return
        if self.pos == 0:
            if tick.last_price > self.donchian_channel_high:
                self.write_log(f"{tick.vt_symbol}: 当前价{tick.last_price}>唐奇安通道上轨{self.donchian_channel_high}，买入1个Unit(持多仓): {self.unit} 手")
                self.buy(tick.last_price * 1.01, self.unit)
            elif tick.last_price < self.donchian_channel_low:  # 当前价<唐奇安通道下轨，卖出1个Unit；(持空仓)
                self.write_log(f"{tick.vt_symbol}: 当前价{tick.last_price}<唐奇安通道下轨{self.donchian_channel_low}，卖出1个Unit(持空仓): {self.unit} 手")
                self.short(tick.last_price * 0.99, self.unit)
        else:
            self.high_price = max(self.high_price, tick.last_price)
            self.low_price = min(self.low_price, tick.last_price)
            if self.pos > 0:  # 持多单
                # 加仓策略: 如果是多仓且行情最新价在上一次建仓（或者加仓）的基础上又上涨了0.5N，就再加一个Unit的多仓,并且风险度在设定范围内(以防爆仓)
                if self.add_pos < self.max_add_pos and tick.last_price >= self.last_price + 0.5 * self.n:
                    self.write_log(f"{tick.vt_symbol}: 最新价{tick.last_price}大于上次调仓价{self.last_price}+0.5*{self.n}，加{self.unit}手多仓")
                    self.buy(tick.last_price * 1.01, self.unit)
                # 止损策略: 如果是多仓且行情最新价在上一次建仓（或者加仓）的基础上又下跌了2N，就卖出全部头寸止损
                elif tick.last_price <= self.last_price - 2 * self.n:
                    self.write_log(f"{tick.vt_symbol}: 最新价{tick.last_price}小于上次调仓价{self.last_price}-2*{self.n}，止损")
                    self.sell(tick.last_price * 0.99, self.pos)
                # 止盈策略: 如果是多仓且行情最新价跌破了10日唐奇安通道的下轨，就清空所有头寸结束策略,离场
                elif tick.last_price < self.high_price - 3 * self.n or tick.last_price <= self.short_donchian_channel_low:
                    self.write_log(f"{tick.vt_symbol}: 止盈")
                    self.sell(tick.last_price * 0.99, self.pos)
            elif self.pos < 0:  # 持空单
                # 加仓策略: 如果是空仓且行情最新价在上一次建仓（或者加仓）的基础上又下跌了0.5N，就再加一个Unit的空仓,并且风险度在设定范围内(以防爆仓)
                if self.add_pos < self.max_add_pos and tick.last_price <= self.last_price - 0.5 * self.n:
                    self.write_log(f"{tick.vt_symbol}: 最新价{tick.last_price}小于上次调仓价{self.last_price}-0.5*{self.n}，加{self.unit}手多仓")
                    self.short(tick.last_price * 0.99, self.unit)
                # 止损策略: 如果是空仓且行情最新价在上一次建仓（或者加仓）的基础上又上涨了2N，就平仓止损
                elif tick.last_price >= self.last_price + 2 * self.n:
                    self.write_log(f"{tick.vt_symbol}: 最新价{tick.last_price}大于上次调仓价{self.last_price}+2*{self.n}，止损")
                    self.cover(tick.last_price * 1.01, -self.pos)
                # 止盈策略: 如果是空仓且行情最新价升破了10日唐奇安通道的上轨，就清空所有头寸结束策略,离场
                elif tick.last_price > self.low_price + 3 * self.n or tick.last_price >= self.short_donchian_channel_high:
                    self.write_log(f"{tick.vt_symbol}: 止盈")
                    self.cover(tick.last_price * 1.01, -self.pos)
        self.put_event()

    def update_param(self):
        if not self.inited:
            return
        self.n = self.am.atr(self.atr_day_length)
        # 买卖单位
        self.unit = max(1, int((self.balance * self.risk_factor) / (self.multiplier * 2 * self.n)))
        # 唐奇安通道上轨：前N个交易日的最高价
        self.donchian_channel_high = max(self.am.high[-self.donchian_channel_open_position:])
        # 唐奇安通道下轨：前N个交易日的最低价
        self.donchian_channel_low = min(self.am.low[-self.donchian_channel_open_position:])
        self.short_donchian_channel_high = max(self.am.high[-self.donchian_channel_stop_profit:])
        self.short_donchian_channel_low = min(self.am.low[-self.donchian_channel_stop_profit:])

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return
        self.update_param()
        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        if trade.offset == Offset.OPEN:
            self.last_price = trade.price
            self.high_price = max(self.high_price, trade.price)
            self.low_price = min(self.low_price, trade.price)
            self.add_pos += 1
        else:
            self.high_price = 0.0
            self.low_price = 1e9
            self.add_pos = 0
            self.last_price = 0
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
