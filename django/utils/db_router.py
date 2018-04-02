class MasterSlaveDBRouter(object):
    """读写分离路由"""
    def db_for_read(self, model, **hints):
        """读"""
        return "slave"

    def db_for_write(self, model, **hints):
        """写"""
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """允许关联查询"""
        return True