import json

class FundRateConfig:
    '''
        参数配置
    '''
    
    def __init__(self):
        self.platform = 'binance'
        self.api_key = ''
        self.api_secret = ''
        self.spot_price_asset = 'USDT'
        self.spot_price_asset_precision = 1e-08
        self.future_price_asset = 'USDT'
        self.future_price_asset_precision = 1e-08
        self.trade_symbol_pool_count = 50
        self.trade_symbol_leverage = 5
        self.position_symbol_pool_count = 60
        self.fund_rate_history_count = 60
        self.single_max_trade_amount = 50
        self.single_min_trade_amount = 30
        self.difference_check_flag = True
        self.mode = 'normal'
        self.init_flag = True
        self.init_start_date = '2021-05-09'
        self.init_spot_total_value = '671'
        self.init_future_total_value = '350'
        self.future_risk_warning_threshold = 68
        self.risk_radio_limit = 0
        self.deposit_min_fund_rate = 0.0009
        self.deposit_min_premium_rate = 0.0009
        self.withdraw_min_fund_rate = 0.0015
        self.withdraw_min_premium_rate = 0.0015
        self.last_eliminate_min_premium_rate = 0.0015
        self.reduce_min_premium_rate = 0.0015
        self.config_data = { }

    
    def load_config(self, config_file = (None,)):
        '''
        加载配置文件并返回配置信息。
        '''
        configures = { }
        if config_file and config_file:
            with open(config_file) as f:
                data = f.read()
                configures = json.loads(data)

            if not configures:
                print('config json file error!')
                exit(0)


        return configures

    
    def loads(self, config_file, risk_radio = 0):
        ''' Load config file.

        Args:
            config_file: config json file.
        '''
        config_data = self.load_config(config_file)
        if config_data:
            self.config_data = config_data
            self.update_base_config(config_data)
            trade_configs_data = config_data.get('trade_config', [])
            trade_configs_data.sort(key=(lambda x: x['risk_radio_limit']), reverse=True)
            self.load_trade_config(risk_radio, trade_configs_data)

    
    def update_base_config(self, config_data):
        '''
        更新基础参数。
        '''
        base_config_keys = [
            'platform',
            'api_key',
            'api_secret',
            'spot_price_asset',
            'spot_price_asset_precision',
            'future_price_asset',
            'future_price_asset_precision',
            'trade_symbol_pool_count',
            'trade_symbol_leverage',
            'position_symbol_pool_count',
            'fund_rate_history_count',
            'single_max_trade_amount',
            'single_min_trade_amount',
            'difference_check_flag',
            'mode',
            'init_flag',
            'init_start_date',
            'init_spot_total_value',
            'init_future_total_value',
            'future_risk_warning_threshold']
        for key in base_config_keys:
            if key in config_data:
                setattr(self, key, config_data[key])

    
    def load_trade_config(self, risk_radio, trade_configs):
        '''
        加载交易配置。
        '''
        for config in trade_configs:
            if risk_radio >= config.get('risk_radio_limit', 0):
                for key, value in config.items():
                    setattr(self, key, value)
            

    
    def update_config(self, risk_radio = (0,)):
        '''
        更新update fields.
        :param update_fields:
        :return: None

        '''
        config_data = self.config_data
        trade_configs_data = config_data.get('trade_config', [])
        trade_configs_data.sort(key=(lambda x: x['risk_radio_limit']), reverse=True)
        self.load_trade_config(risk_radio, trade_configs_data)


fund_rate_config = FundRateConfig()

