from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings


class FastDFSStorage(Storage):
    """fastdfs存储工具类, 提供给django使用"""
    def __init__(self, client_conf=None, fastdfs_url=None):
        """初始化，设置参数"""
        if client_conf is None:
            client_conf = settings.FASTDFS_CLIENT
        self.client_conf = client_conf

        if fastdfs_url is None:
            fastdfs_url = settings.FASTDFS_URL

        self.fastdfs_url = fastdfs_url

    def _open(self, name, mode='rb'):
        """打开文件时使用"""
        pass

    def _save(self, name, content):
        """保存文件时使用"""
        # content是用户上传过来的文件对象， 如果想获取文件的内容，使用read方法读取

        # 创建fastdfs客户端的工具对象
        client = Fdfs_client(self.client_conf)

        # 借助client客户端，向fastdfs发送文件
        file_data = content.read()  # 读取文件内容
        try:
            ret = client.upload_by_buffer(file_data)
        except Exception as e:
            print(e)
            raise

        # {'Group name': 'group1', 'Status': 'Upload successed.', 'Remote file_id': 'group1/M00/00/00/
        #  wKjzh0_xaR63RExnAAAaDqbNk5E1398.py','Uploaded size':'6.0KB','Local file name':'test'
        #     , 'Storage IP': '192.168.243.133'}
        # 根据返回值进行判断
        if ret.get("Status") == "Upload successed.":
            # 表示上传到fastdfs服务器成功
            file_id = ret.get("Remote file_id")
            # 将文件名返回，django会保存到数据库中
            return file_id
        else:
            # 表示上传到fastdfs服务器时出现了问题
            raise Exception("上传FastDFS服务器出现问题")

    def exists(self, name):
        """django用来判断文件是否存在"""
        return False

    def url(self, name):
        """返回文件的完整路径名，django会调用"""
        return self.fastdfs_url + name










