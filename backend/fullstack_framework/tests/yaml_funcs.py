"""
@Filename:   /yaml_funcs
@Time:        2023/5/19 21:33
@Describe:    ...
"""
import base64
import hashlib
import time

import rsa
from fullstack_framework.commons import settings


def md5(s):
    # md5散列算法
    # 1. 同一个算法的结果，长度相同
    # 2. 不能逆运算
    # 3. 可以碰撞

    res = hashlib.md5(s.encode("utf-8")).hexdigest()  # 16进制字符
    print(s, res)
    return res


def base_64(s):
    # Base64 是编码方式
    # 1.可以将【任意】的二进制 编码为常见字符 （大小写字母、数字、+=）
    # 2.可以逆运算
    # 3. 没有安全性

    data = s.encode("utf-8")  # 二进制

    res_data = base64.b64encode(data)  # 进行base64编码

    res = res_data.decode("utf-8")  # 字符串

    return res


def ras(s):
    # RSA 真正意义上非对称加密算法
    # 对称加密：加密的密钥，和解密的密钥，相同， 能加密，就能够解密
    # 非对称加密：加密的密钥，和解密的密钥，不相同， 能加密，也不能解密
    # 需要安装第三方依赖

    with open(settings.rsa_pub_path, "rb") as f:
        # print(f.read())
        pubkey = rsa.PublicKey.load_pkcs1(f.read())  # 加载公钥

    data = rsa.encrypt(s.encode("utf-8"), pubkey)  # 加密结果是二进制

    res_data = base64.b64encode(data)  # 进行base64编码

    res = res_data.decode("utf-8")  # 字符串

    return res


def get_statu(referer):
    s = referer[86 + len("_statu%3D") :]

    return s


def x3(s):
    return s * 3


def time_join_str(s):
    return str(int(time.time())) + s


if __name__ == "__main__":
    md5("admin")
