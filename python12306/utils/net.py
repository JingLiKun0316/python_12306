import copy
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import requests
import urllib3
from urllib3.util import parse_url

from python12306.comonexception import ResponseError, ResponseCodeError
from python12306.utils.log import Log
from python12306.utils.cdn import CdnStorage

def send_captcha_requests(session, urlmapping_obj, params=None, data=None, **kwargs):
    """
    xml data example:
        <HashMap>
        <result_message>验证码校验失败,信息为空</result_message>
        <result_code>8</result_code>
        </HashMap>
        format result data.
    """
    session.headers.update(urlmapping_obj.headers)
    try:
        response = session.request(method=urlmapping_obj.method,
                                   url=urlmapping_obj.url,
                                   params=params,
                                   data=data,
                                   timeout=10,
                                   # allow_redirects=False,
                                   **kwargs)
    except requests.RequestException as e:
        Log.w(e)
        Log.w("请求{0}异常 ".format(urlmapping_obj.url))
        raise ResponseError
    Log.d(urlmapping_obj.url)
    if response.status_code == requests.codes.ok:
        if 'xhtml+xml' in response.headers['Content-Type']:
            data = response.text
            root = ET.fromstring(data)
            message = root.find('result_message').text
            code = root.find('result_code').text
            return {"result_message": message, "result_code": code}
        elif 'json' in response.headers['Content-Type']:
            return response.json()
        else:
            Log.w(response.url)
            Log.w(response.status_code)
            raise ResponseError
    else:
        Log.w(response.url)
        Log.w(response.status_code)
        raise ResponseCodeError


def get_captcha_image(session, urlmapping_obj, params=None, data=None, **kwargs):
    """
    xml data example:
        <HashMap>
            <result_message>生成验证码成功</result_message>
            <result_code>0</result_code>
            <image>imagedata<image>
        </HashMap>
        format result data.
    """
    session.headers.update(urlmapping_obj.headers)
    try:
        response = session.request(method=urlmapping_obj.method,
                                   url=urlmapping_obj.url,
                                   params=params,
                                   data=data,
                                   timeout=10,
                                   # allow_redirects=False,
                                   **kwargs)
    except requests.RequestException as e:
        Log.w(e)
        Log.w("请求{0}异常 ".format(urlmapping_obj.url))
        raise ResponseError
    if response.status_code == requests.codes.ok:
        if 'xhtml+xml' in response.headers['Content-Type']:
            data = response.text
            root = ET.fromstring(data)
            message = root.find('result_message').text
            code = root.find('result_code').text
            image = root.find('image').text
            return {"result_message": message, "code": code, 'image': image}
        elif 'json' in response.headers['Content-Type']:
            return response.json()
        else:
            Log.w(response.url)
            Log.w(response.status_code)
            raise ResponseCodeError
    else:
        Log.w(response.url)
        Log.w(response.status_code)
        raise ResponseCodeError


def send_requests(session, urlmapping_obj, params=None, data=None, **kwargs):
    time.sleep(0.5)
    session.headers.update(urlmapping_obj.headers)
    if urlmapping_obj.method.lower() == 'post':
        session.headers.update(
            {"Content-Type": r'application/x-www-form-urlencoded; charset=UTF-8'}
        )
    else:
        session.headers.pop("Content-Type", None)
    if urlmapping_obj.type.lower() == 'cdn' and CdnStorage.status and CdnStorage.result:
        # use cdn to check ticket
        cdn_ip = CdnStorage.choose_one().ip
        request_url = urlmapping_obj.url.replace(
            parse_url(urlmapping_obj.url).host,
            cdn_ip)
        Log.v("当前正在使用CDN IP 为{0}".format(cdn_ip))
    else:
        request_url = urlmapping_obj.url

    try:
        Log.d("请求 url {url}".format(url=request_url))
        try:
            if urlmapping_obj.type.lower() == 'cdn':
                # only query data disable warning
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = session.request(method=urlmapping_obj.method,
                                           url=request_url,
                                           params=params,
                                           data=data,
                                           timeout=10,
                                           # allow_redirects=False,
                                           verify=False,
                                           **kwargs)
            else:
                response = session.request(method=urlmapping_obj.method,
                                           url=request_url,
                                           params=params,
                                           data=data,
                                           timeout=10,
                                           **kwargs)
        except requests.RequestException as e:
            Log.w(e)
            Log.w("请求{0}异常 ".format(request_url))
            raise ResponseError
        if params:
            Log.d("{url} Get 参数 {data}".format(url=request_url,
                                               data=params))
        if data:
            Log.d("{url} Post 参数 {data}".format(url=request_url,
                                                data=data))
        Log.d("返回response url {url}".format(url=response.url))
        if response.status_code == requests.codes.ok:
            if 'xhtml+xml' in response.headers['Content-Type']:
                data = response.text
                root = ET.fromstring(data)
                result = {v.tag: v.text for v in root.getchildren()}
                return result
            if 'json' in response.headers['Content-Type'] and urlmapping_obj.type.lower() != 'text':
                result = response.json()
                Log.d("{url} 返回值 {result}".format(url=response.url,
                                                  result=result))
                return result
            # other type
            return response.text
        elif response.status_code == requests.codes.found:
            if 'leftTicket/query' in request_url and 'json' in response.headers['Content-Type']:
                Log.v("检测到查票接口有变, 更改为新的查票接口")
                result = response.json()
                try:
                    url = result["c_url"]
                    urlmapping_obj.url = urljoin("https://kyfw.12306.cn/otn/", url)
                except KeyError:
                    Log.w(response.url)
                    Log.w(response.status_code)
                    Log.w("更改查票接口失败")
            else:
                Log.w(response.url)
                Log.w(response.status_code)
                Log.w("返回状态码有问题")
        else:
            Log.w(response.url)
            Log.w(response.status_code)
            Log.w("返回状态码有问题")
    except Exception as e:
        Log.e(e)
    return None


def submit_response_checker(response, ok_columns, ok_code, msg="OK"):
    back_response = copy.copy(response)
    if not isinstance(response, (list, dict)):
        return False, '数据非json数据'
    messages = back_response.get("messages", "")
    if messages and isinstance("messages", list):
        Log.v("\n".join(messages))
    if messages and isinstance("messages", str):
        Log.v(messages)
    for v in ok_columns:
        response = back_response
        nest = v.split('.')
        for v1 in nest:
            r = response.get(v1, None)
            if not r:
                return False, "字段不存在检查失败"
            else:
                response = r
        if response != ok_code:
            return False, "字段状态不存在"
    del back_response
    return True, msg


def json_status(json_response, check_column, ok_code=0):
    """
    :param ok_code: ok code.
    :param json_response: json_response
    :param check_column: check column, add column missing message
    :return:
    """
    if not isinstance(json_response, (list, dict)):
        return False, '数据非json数据'
    code = json_response.get('result_code', None)
    status = code == ok_code or code == 0 or code == '0'
    if status:
        return status, "OK"
    else:
        return status, " ".join(["{column} not found".format(
            column=v
        ) for v in check_column if v not in json_response])
