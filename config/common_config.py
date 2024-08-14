import json

class CommonConfig:
    '''
        通用配置
    '''
    
    def __init__(self):
        self.proxy = True
        self.tele_flag = True
        self.tele_token = ''
        self.chat_id = ''

    
    def loads(self, config_file = (None,)):
        '''
        Load config file.
        Args:
            config_file: config json file.
        '''
        configures = { }
        if config_file:
            
            try:
                with open(config_file) as f:
                    data = f.read()
                    configures = json.loads(data)

                if not None:
                    pass
            finally:
                pass
            e = None
            
            try:
                print(e)
                exit(0)
            finally:
                e = None
                del e
            e = None
            del e
            if not configures:
                print('config json file error!')
                exit(0)


        self._update(configures)

    
    def _update(self, update_fields):
        '''
        更新update fields.
        :param update_fields:
        :return: None

        '''
        for k, v in update_fields.items():
            setattr(self, k, v)


common_config = CommonConfig()
