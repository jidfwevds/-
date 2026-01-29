import os
import re
import json
import time
import ssl
import shutil
import subprocess
import requests
import logging
from urllib.parse import urlparse, unquote, parse_qs, urlunparse
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# 全局配置
ROOT_DOWNLOAD_DIR = "./video_downloads"
FFMPEG_PATH = "C:\\Users\\86187\\Desktop\\ffmpeg-7.1-essentials_build\\bin\\ffmpeg.exe"
CHROME_USER_DATA_DIR = r"D:\毕设\cookies"
CHROMEDRIVER_PATH = r"C:\Users\86187\.wdm\drivers\chromedriver\win64\136.0.7103.113\chromedriver-win32\chromedriver.exe"
MY_WEIBO_COOKIE = "XSRF-TOKEN=J2KRRxwUsrd_aus0XESLHC60; SCF=AvUal8CW2IN9JIsV5sbLou-TWBSrcNG0HqKtQI4Uc8g5tV_OGL9m7T6Bkxf8O4ml07M0D2ZVoVbf57WyAcZwtFw.; SUB=_2A25EaanpDeRhGeFJ7FcY9SrNyjuIHXVnBqMhrDV8PUNbmtANLUjjkW9NfzcfHnCFTvudHiWFhBB9mTUnhmCiuVlC; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WWGRUaxPyQderskNVSeSn-h5JpX5KzhUgL.FoMNS0-4SKBpeKM2dJLoIEXLxK-L1hMLBK5LxKqL1-eLBKnLxK-LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.LB.-L1K.t; ALF=02_1771398841; WBPSESS=OxdrHbRWIHqisU0tUx18uvcRrLDUOqRxfX0_LNUDVaHTMccwPCaKozM902u0zqwkSXXte_4pKYfwXoYlkepcU6DGv8AgdXnWDDf_w2p6jimQwibrpSIi8W8C7yJvhURXXp9rbJI1Q4Rh6KF5yxqY1w=="
PLATFORM_RULES = {
    "douyin": r"douyin\.com|dy\.url|iesdouyin\.com|v\.douyin\.com",
    "kuaishou": r"kuaishou\.com|kwaishou\.com|v\.kuaishou\.com",
    "bilibili": r"bilibili\.com|b23\.tv",
    "xiaohongshu": r"xiaohongshu\.com|xhslink\.com",
    "weibo": r"weibo\.com|video\.weibo\.com",
}

requests.packages.urllib3.disable_warnings()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# 通用工具函数
def create_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def identify_platform(url):
    for platform, pattern in PLATFORM_RULES.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return None


def safe_filename(title):
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    return safe_title.strip()


# 小红书下载模块
class XiaohongshuDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
            'Cookie': 'acw_tc=0a00dcc017688072719092301ea3f8b45b759b46cf06e464473210415f3ad1; abRequestId=3bcf8b6b-9151-5846-bced-e31e9c0e9c6a; webBuild=5.7.0; xsecappid=xhs-pc-web; loadts=1768807273378; a1=19bd52113a4t8xs4ccph83uhz9jqhfqdse803omd350000916951; webId=b315f72140739ef13488e6faf1c47d2f; gid=yjDf2JyJ88MjyjDf2Jyyqdl6049YCM4SSUxYYfqq7xujV828AxiAfq888jyKj2y8djf0fYW4; websectiga=634d3ad75ffb42a2ade2c5e1705a73c845837578aeb31ba0e442d75c648da36a; sec_poison_id=6eaea7d6-7e59-4f28-b9ce-48577db4f43b; web_session=040069b3a8fd5b2e170d2895583b4b28679b91; id_token=VjEAAFzIyzSSvERknBOhi4hRgsMdhx4KlTNvIV6Wy1QCoyEJ0PE/9Clj7lXMFnfv1BeBAWn4MRNkL2BMh2J6LyzNGWfY0/tdxB1uNck6aXfhN848PC40alMKsZQyArTw9nSjsBRW; unread={%22ub%22:%2269698cf9000000001a01f471%22%2C%22ue%22:%22696cb161000000000b010177%22%2C%22uc%22:29}',
        }

    def resolve_short_url(self, short_url):
        parsed_url = urlparse(short_url)
        if parsed_url.netloc == 'xhslink.com' and short_url.startswith('http://'):
            short_url = short_url.replace('http://', 'https://')

        try:
            response = requests.head(short_url, headers=self.headers, allow_redirects=False, timeout=10)
            if response.status_code in [301, 302, 303, 307, 308]:
                return response.headers.get('Location')
            else:
                response = requests.get(short_url, headers=self.headers, allow_redirects=True, timeout=10)
                return response.url
        except Exception:
            return None

    def get_note_url(self, url):
        parsed_url = urlparse(url)
        if parsed_url.netloc == 'xhslink.com' and url.startswith('http://'):
            url = url.replace('http://', 'https://')

        if 'xhslink.com' in url:
            real_url = self.resolve_short_url(url)
            if not real_url or 'xiaohongshu.com' not in real_url:
                return None
            return real_url
        else:
            return url

    def extract_video_url(self, note_url):
        try:
            response = requests.get(note_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            html = response.text

            video_url = None
            if '"masterUrl":"' in html:
                video_url = re.findall('"masterUrl":"(.*?)"', html)[0].replace('\\u002F', '/')
            elif '"videoUrl":"' in html:
                video_url = re.findall('"videoUrl":"(.*?)"', html)[0].replace('\\u002F', '/')
            else:
                video_patterns = [r'"stream":\s*{"url":\s*"(.*?)"', r'"src":\s*"(https?://[^"]+\.mp4[^"]*)"']
                for pattern in video_patterns:
                    matches = re.findall(pattern, html)
                    if matches:
                        video_url = matches[0].replace('\\u002F', '/')
                        break

            if not video_url:
                return None

            if video_url.startswith('http://'):
                video_url = video_url.replace('http://', 'https://')
            return video_url
        except Exception:
            return None

    def download_video(self, video_url, save_dir):
        if not video_url:
            return False

        timestamp = int(time.time())
        save_path = os.path.join(save_dir, f'xhs_video_{timestamp}.mp4')
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        print("开始下载小红书视频...")
        try:
            response = requests.get(video_url, headers=self.headers, timeout=30, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            downloaded = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r下载进度: {percent:.1f}%", end='')

            print(f"\n小红书视频下载成功! 保存路径: {save_path}")
            return True
        except Exception:
            print("\n小红书视频下载失败")
            return False

    def download_from_url(self, url, save_dir):
        real_url = self.get_note_url(url)
        if not real_url:
            return False
        video_url = self.extract_video_url(real_url)
        if not video_url:
            return False
        return self.download_video(video_url, save_dir)


# 微博下载模块
def extract_video_fid(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'fid' in query_params and query_params['fid']:
        fid = query_params['fid'][0]
        if re.match(r'\d+:\d+', fid):
            return fid

    pattern = r'show/(\d+:\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    pattern_encoded = r'url=([^&]+)'
    match_encoded = re.search(pattern_encoded, url)
    if match_encoded:
        encoded_url = match_encoded.group(1)
        decoded_url = unquote(encoded_url)
        sub_match = re.search(r'show/(\d+:\d+)', decoded_url)
        if sub_match:
            return sub_match.group(1)

    return None


def get_video_info_from_api(fid):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://weibo.com/',
        'Cookie': MY_WEIBO_COOKIE.strip(),
        'X-Requested-With': 'XMLHttpRequest',
        'XSRF-TOKEN': MY_WEIBO_COOKIE.strip().split('XSRF-TOKEN=')[1].split(';')[
            0] if 'XSRF-TOKEN=' in MY_WEIBO_COOKIE else '',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

    session = requests.Session()
    session.headers.update(headers)
    session.verify = False
    session.trust_env = False
    session.cookies.update(
        requests.utils.dict_from_cookiejar(requests.get("https://weibo.com/", headers=headers, verify=False).cookies))

    try:
        api_url = "https://weibo.com/tv/api/component"
        params = {
            'page': f'/tv/show/{fid}',
            'component': 'PlayPage',
            'version': 'v1.0',
            '__rnd': int(time.time() * 1000)
        }
        post_data = {
            'data': json.dumps({
                'Component_Play_Playinfo': {
                    'oid': fid,
                    'pl_type': 'video',
                    'pic_ext': '',
                    'is_show_limit': 1
                }
            })
        }

        response = session.post(
            api_url,
            params=params,
            data=post_data,
            timeout=15,
            allow_redirects=False
        )
        response.raise_for_status()
        api_data = response.json()

        video_info = api_data['data']['Component_Play_Playinfo']
        video_url = None
        for key in ['mp4_hd_url', 'mp4_ld_url', 'stream_url']:
            if key in video_info and video_info[key]:
                video_url = video_info[key].replace('\\/', '/').replace('\u0026', '&')
                break

        title = video_info.get('title', f'微博_{fid}')
        return video_url, title, session
    except Exception:
        return None, None, None


def download_weibo_video(video_url, title, session, save_dir):
    if not video_url:
        return False

    title = safe_filename(title)[:100]
    filename = f"{title}_{int(time.time())}.mp4"
    filepath = os.path.join(save_dir, filename)

    download_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://weibo.com/tv/show/{extract_video_fid(video_url) if extract_video_fid(video_url) else "1034:0"}',
        'Cookie': MY_WEIBO_COOKIE.strip(),
        'Range': 'bytes=0-',
        'Sec-Fetch-Dest': 'video',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
        'Cache-Control': 'no-cache',
    }

    try:
        print("\n开始下载微博视频...")
        response = session.get(
            video_url,
            headers=download_headers,
            stream=True,
            timeout=60,
            allow_redirects=True
        )
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r下载进度: {percent:.1f}%", end='')

        print(f"\n微博视频下载成功! 保存路径: {filepath}")
        return True
    except Exception:
        print("\n微博视频下载失败")
        return False


def weibo_download_from_url(url, save_dir):
    fid = extract_video_fid(url)
    if not fid:
        return False
    video_url, title, session = get_video_info_from_api(fid)
    if not video_url or not session:
        return False
    return download_weibo_video(video_url, title, session, save_dir)


# ===================== 快手下载模块 =====================
class KuaishouVideoDownloader:
    """快手视频下载器 - 专门适配集成环境"""

    def __init__(self, save_dir="快手", headless=False):
        """
        初始化快手视频下载器
        :param save_dir: 视频保存目录
        :param headless: 是否使用无头模式（集成中改为False）
        """
        self.driver = None
        self.save_dir = save_dir
        self.headless = headless  # 重要：改为False显示浏览器

        # 创建保存目录
        os.makedirs(save_dir, exist_ok=True)

        # 禁用SSL警告
        requests.packages.urllib3.disable_warnings()

    def setup_driver(self):
        """设置Selenium浏览器驱动 - 完全复制单独版本的配置"""
        try:
            chrome_options = Options()

            # 1. 使用有界面模式（重要！）
            if self.headless:
                chrome_options.add_argument('--headless=new')  # 新版无头模式
            else:
                chrome_options.add_argument('--start-maximized')  # 最大化窗口显示

            # 2. 核心：复用本地登录的Cookie目录
            chrome_options.add_argument(f'user-data-dir={CHROME_USER_DATA_DIR}')

            # 3. 浏览器指纹伪装
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images=False')
            chrome_options.add_argument('--disable-javascript=False')
            chrome_options.add_argument('--lang=zh-CN,zh;q=0.9')
            chrome_options.add_argument('--accept-lang=zh-CN,zh')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--ignore-certificate-errors')

            # 4. 禁用自动化特征
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.page_load_strategy = 'normal'

            # 5. 创建浏览器实例
            try:
                # 尝试使用指定路径
                if CHROMEDRIVER_PATH and os.path.exists(CHROMEDRIVER_PATH):
                    service = Service(executable_path=CHROMEDRIVER_PATH)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    # 让系统自动查找
                    self.driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                print(f"❌ Chrome驱动创建失败: {e}")
                # 最后尝试不使用Service
                self.driver = webdriver.Chrome(options=chrome_options)

            # 6. 注入反检测脚本（和单独版本完全一致）
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                    window.chrome = {runtime: {}};
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                """
            })

            print("🎬 快手浏览器启动成功（有界面模式）")
            return True

        except Exception as e:
            print(f"❌ 浏览器启动失败: {e}")
            return False

    def clean_kuaishou_url(self, url):
        """清理快手URL（和单独版本一致）"""
        print(f"🔗 解析URL: {url}")

        # 解码URL
        url = unquote(url.strip())

        # 解析URL
        parsed = urlparse(url)

        # 提取视频ID
        video_id = None

        # 方法1: 从路径中提取ID
        path_match = re.search(r'/short-video/([a-zA-Z0-9]+)', parsed.path)
        if path_match:
            video_id = path_match.group(1)
            print(f"📹 提取到视频ID: {video_id}")

        # 方法2: 处理短链接格式
        if not video_id:
            if 'v.kuaishou.com' in url or parsed.path.startswith('/f/') or 'kuaishou.com/f/' in url:
                print("🔍 检测到移动端/短链接，开始解析重定向...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Referer': 'https://www.kuaishou.com/',
                        'Cookie': ''
                    }
                    response = requests.get(url, headers=headers, allow_redirects=True, timeout=15, verify=False)
                    final_url = response.url
                    print(f"🔄 短链接重定向到: {final_url}")
                    # 递归清理重定向后的URL
                    return self.clean_kuaishou_url(final_url)
                except Exception as e:
                    print(f"❌ 解析短链接失败: {e}")

        # 构建干净的URL
        if video_id:
            clean_url = f"https://www.kuaishou.com/short-video/{video_id}"
            print(f"✨ 生成标准URL: {clean_url}")
            return clean_url
        else:
            clean_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                '', '', ''
            ))
            print(f"🧹 清理后URL: {clean_url}")
            return clean_url

    def extract_video_info(self, url):
        """提取视频信息（优化版）"""
        try:
            # 启动浏览器
            if not self.driver:
                if not self.setup_driver():
                    return None, None

            clean_url = self.clean_kuaishou_url(url)
            print(f"🌐 访问页面: {clean_url}")

            # 访问页面
            self.driver.get(clean_url)

            # 关键：智能等待页面加载
            print("⏳ 智能等待页面加载...")

            # 等待页面基本加载完成
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                print("⚠️ 页面body加载超时，继续执行")

            # 等待更长时间确保内容加载
            time.sleep(3)

            # 尝试查找视频元素
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "video"))
                )
                print("✅ 视频元素加载完成")
            except:
                print("⚠️ 未找到video标签，继续尝试")

            # 再次等待确保完全加载
            time.sleep(2)

            # 获取页面标题
            page_title = self.driver.title
            print(f"📝 页面标题: {page_title}")

            # 如果页面标题为空，可能页面没有正确加载
            if not page_title or page_title == "快手":
                print("⚠️ 页面可能未正确加载，尝试刷新...")
                self.driver.refresh()
                time.sleep(3)
                page_title = self.driver.title
                print(f"📝 刷新后页面标题: {page_title}")

            # 获取页面HTML以便调试
            try:
                page_html = self.driver.page_source
                if len(page_html) < 1000:
                    print("⚠️ 页面HTML内容过少，可能被反爬")
            except:
                pass

            # 多种方式获取视频URL
            video_url = None

            # 方法1: 尝试9种不同方式（和单独版本一样）
            video_elem = None
            try:
                video_elem = self.driver.find_element(By.TAG_NAME, "video")
            except:
                print("⚠️ 未找到video元素")

            # 优先从video元素属性获取
            if video_elem:
                attributes_to_check = ['data-src', 'data-play-url', 'srcset', 'src', 'data-video-url']
                for attr in attributes_to_check:
                    try:
                        url_val = video_elem.get_attribute(attr)
                        if url_val and '.mp4' in url_val.lower():
                            video_url = url_val
                            print(f"✅ 从video[{attr}]获取到视频URL")
                            break
                    except:
                        continue

            # 方法2: JavaScript获取
            if not video_url:
                js_scripts = [
                    "return document.querySelector('video')?.src",
                    "return document.querySelector('video source')?.src",
                    "return Array.from(document.querySelectorAll('video')).map(v => v.src).find(src => src && src.includes('.mp4'))",
                    "return document.querySelector('.player-video')?.src",
                    "return document.querySelector('[data-video]')?.dataset.video",
                ]
                for js_script in js_scripts:
                    try:
                        result = self.driver.execute_script(js_script)
                        if result and '.mp4' in result.lower():
                            video_url = result
                            print(f"✅ 通过JavaScript获取到视频URL")
                            break
                    except:
                        continue

            # 方法3: 页面源码正则匹配
            if not video_url:
                try:
                    page_html = self.driver.page_source
                    mp4_patterns = [
                        r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
                        r'src="(https?://[^"]+\.mp4[^"]*)"',
                        r'"playUrl":"([^"]+\.mp4[^"]*)"',
                        r'"mainUrl":"([^"]+\.mp4[^"]*)"',
                        r'data-src="([^"]+\.mp4[^"]*)"',
                        r'data-play-url="([^"]+\.mp4[^"]*)"',
                    ]
                    for pattern in mp4_patterns:
                        matches = re.findall(pattern, page_html, re.IGNORECASE)
                        if matches:
                            for match in matches:
                                if isinstance(match, tuple):
                                    match = match[0]
                                if '.mp4' in match.lower() and ('kuaishoucdn' in match or 'aliyuncs' in match):
                                    video_url = match
                                    print(f"✅ 从页面源码找到视频URL")
                                    break
                        if video_url:
                            break
                except Exception as e:
                    print(f"搜索页面源码失败: {e}")

            # 方法4: 网络请求监控
            if not video_url:
                try:
                    network_js = """
                    return window.performance.getEntriesByType('resource')
                        .filter(entry => entry.name.includes('.mp4'))
                        .map(entry => entry.name);
                    """
                    video_urls = self.driver.execute_script(network_js)
                    if video_urls and len(video_urls) > 0:
                        for url in video_urls:
                            if '.mp4' in url.lower():
                                video_url = url
                                print(f"✅ 从网络请求中获取到视频URL")
                                break
                except:
                    pass

            if not video_url:
                print("❌ 无法获取视频URL")
                print("💡 可能原因：")
                print("   1. Cookie失效或未登录")
                print("   2. 页面未完全加载")
                print("   3. 视频已下架或不可用")

                # 输出页面信息用于调试
                try:
                    print(f"📄 页面URL: {self.driver.current_url}")
                    print(f"🔍 页面内容前500字符: {self.driver.page_source[:500]}")
                except:
                    pass

                return None, None

            # 清理视频URL
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            elif video_url.startswith('/'):
                parsed_url = urlparse(clean_url)
                video_url = f"{parsed_url.scheme}://{parsed_url.netloc}{video_url}"

            # 验证视频URL
            if not video_url.startswith('http'):
                print(f"⚠️ 视频URL格式异常: {video_url}")
                if video_url.startswith('blob:'):
                    print("❌ 拿到blob协议！Cookie可能失效")
                    return None, None
                else:
                    video_url = 'https:' + video_url if video_url.startswith('//') else f'https://{video_url}'

            print(f"✅ 成功获取视频URL: {video_url[:100]}...")
            return page_title, video_url

        except Exception as e:
            print(f"❌ 提取视频信息失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None

    def download_video(self, video_url, filename=None, max_retries=3):
        """下载视频"""
        if not video_url:
            print("❌ 视频URL为空")
            return False

        # 生成文件名
        if not filename:
            video_id_match = re.search(r'/([^/?]+\.mp4)', video_url)
            if video_id_match:
                filename = video_id_match.group(1)
            else:
                filename = f"kuaishou_video_{int(time.time())}.mp4"

        filepath = os.path.join(self.save_dir, filename)

        print(f"💾 开始下载视频: {filename}")

        # 准备请求头（和单独版本一致）
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': self.driver.current_url if self.driver else 'https://www.kuaishou.com/',
            'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
            'Accept-Encoding': 'identity',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'video',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }

        # 从浏览器获取Cookie
        if self.driver:
            try:
                cookies = self.driver.get_cookies()
                cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
                headers['Cookie'] = cookie_str
                print(f"🍪 使用Cookie: {cookie_str[:50]}...")
            except Exception as e:
                print(f"⚠️ 获取Cookie失败: {e}")

        # 下载视频
        for attempt in range(max_retries):
            try:
                print(f"🔄 下载尝试 {attempt + 1}/{max_retries}")

                response = requests.get(video_url, headers=headers, stream=True, timeout=30, verify=False)

                if response.status_code == 200:
                    total_size = int(response.headers.get('content-length', 0))

                    if total_size > 0:
                        print(f"📊 视频大小: {total_size / 1024 / 1024:.2f} MB")

                    downloaded = 0
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    print(
                                        f"\r📥 下载进度: {percent:.1f}% ({downloaded / 1024 / 1024:.2f}MB/{total_size / 1024 / 1024:.2f}MB)",
                                        end='')

                    if os.path.exists(filepath) and os.path.getsize(filepath) > 10240:
                        actual_size = os.path.getsize(filepath)
                        print(f"\n✅ 下载完成! 文件大小: {actual_size / 1024 / 1024:.2f} MB")
                        print(f"💾 保存路径: {filepath}")

                        # 验证文件
                        try:
                            with open(filepath, 'rb') as f:
                                header = f.read(12)
                                if header[:4] == b'ftyp' or header[4:8] == b'ftyp':
                                    print("✅ 文件验证通过: 有效的MP4视频")
                                else:
                                    print("⚠️ 文件可能不是标准MP4格式")
                        except:
                            pass

                        return True
                    else:
                        print("❌ 下载的文件太小或不存在")
                        if os.path.exists(filepath):
                            os.remove(filepath)

                elif response.status_code == 403:
                    print("❌ 403拒绝访问 → 原因：Cookie失效/未登录")
                    return False
                elif response.status_code == 404:
                    print("❌ 404 URL过期或无效")
                    return False
                else:
                    print(f"❌ 下载失败，状态码: {response.status_code}")

            except requests.exceptions.Timeout:
                print("❌ 请求超时")
            except requests.exceptions.ConnectionError:
                print("❌ 连接错误")
            except Exception as e:
                print(f"❌ 下载出错: {e}")

            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"⏱️ 等待{wait_time}秒后重试...")
                time.sleep(wait_time)

        print("❌ 下载失败，已达最大重试次数")
        return False

    def download_from_url(self, url, save_dir):
        """
        完整下载流程 - 适配集成接口
        :param url: 快手视频URL
        :param save_dir: 保存目录
        :return: 下载成功bool
        """
        print("=" * 60)
        print("🚀 快手视频下载器启动（集成适配版）")
        print("=" * 60)

        try:
            # 更新保存目录
            self.save_dir = save_dir
            os.makedirs(self.save_dir, exist_ok=True)

            print(f"📁 保存到: {self.save_dir}")
            print(f"🔗 处理URL: {url}")

            # 提取视频信息
            title, video_url = self.extract_video_info(url)
            if not video_url:
                print("❌ 无法获取视频URL，下载终止")
                return False

            # 生成文件名
            if title and title not in ['快手', '快手短视频', '视频'] and len(title) > 3:
                safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
                filename = f"{safe_title[:50]}_{int(time.time())}.mp4"
            else:
                video_id_match = re.search(r'/short-video/([a-zA-Z0-9]+)', url)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    filename = f"kuaishou_{video_id}.mp4"
                else:
                    filename = f"kuaishou_{int(time.time())}.mp4"

            print(f"📝 文件名: {filename}")

            # 下载视频
            success = self.download_video(video_url, filename)

            if success:
                print("=" * 60)
                print("🎉 快手视频下载成功!")
                print("=" * 60)
            else:
                print("=" * 60)
                print("❌ 快手视频下载失败")
                print("=" * 60)

            return success

        except Exception as e:
            print(f"❌ 快手视频下载失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # 关闭浏览器（重要！）
            self.close_driver()

    def close_driver(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                print("✅ 浏览器已关闭")
            except:
                pass
# 抖音下载模块
class DouyinVideoCrawlerAndDownloader:
    def __init__(self):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_argument("--start-maximized")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
        self.chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        self.chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.media_stream_camera": 2,
            "profile.default_content_setting_values.media_stream_mic": 2,
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.popups": 2,
        })

        self.download_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/',
            'Origin': 'https://www.douyin.com',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }

        self.short_url_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

        self.driver = None
        self.session = requests.Session()
        self.session.headers.update(self.short_url_headers)
        self.session.keep_alive = False
        self.session.verify = False
        self.session.timeout = 30

    def clean_url(self, url):
        if not url:
            return None
        url = url.strip()
        url = re.sub(r'[^\w:/\.\?&=-]', '', url)
        url = re.split(r'\s+', url)[0]
        return url

    def extract_video_id(self, url):
        url = self.clean_url(url)
        if not url:
            return None

        parsed_url = urlparse(url)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if 'modal_id' in query_params:
            return query_params['modal_id'][0]

        video_match = re.search(r'/video/(\d+)', path)
        if video_match:
            return video_match.group(1)

        share_match = re.search(r'/share/video/(\d+)', path)
        if share_match:
            return share_match.group(1)

        note_match = re.search(r'/note/(\d+)', path)
        if note_match:
            return note_match.group(1)

        if any(domain in url for domain in ['v.douyin.com', 'iesdouyin.com']):
            try:
                response = self.session.get(
                    url,
                    headers=self.short_url_headers,
                    allow_redirects=True,
                    timeout=10,
                    verify=False
                )
                final_url = response.url
                return self.extract_video_id(final_url)
            except Exception:
                return None

        numbers = re.findall(r'\d+', url)
        if numbers:
            longest_number = max(numbers, key=len)
            if len(longest_number) >= 15:
                return longest_number

        return None

    def normalize_video_url(self, video_id):
        if not video_id:
            return None
        if video_id.startswith('http'):
            return video_id
        return f"https://www.douyin.com/video/{video_id}"

    def get_video_info(self, video_page_url):
        video_id = self.extract_video_id(video_page_url)
        if not video_id:
            return None

        standard_url = self.normalize_video_url(video_id)

        try:
            service = Service(executable_path=CHROMEDRIVER_PATH)
            self.driver = webdriver.Chrome(
                service=service,
                options=self.chrome_options
            )
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
        except Exception:
            return None

        try:
            self.driver.get(standard_url)
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "video, .xg-video-container, [data-e2e='video-play']"))
                )
            except:
                pass

            time.sleep(8)

            cookies = self.driver.get_cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            self.download_headers['Cookie'] = cookie_str

            logs = self.driver.get_log('performance')
            target_response = None

            for log in logs:
                try:
                    log_json = json.loads(log['message'])['message']
                    if log_json['method'] != 'Network.responseReceived':
                        continue

                    request_url = log_json['params']['response']['url']

                    if ('aweme/detail' in request_url or 'aweme_info' in request_url) and video_id in request_url:
                        try:
                            response_body = self.driver.execute_cdp_cmd('Network.getResponseBody', {
                                'requestId': log_json['params']['requestId']
                            })

                            if response_body.get('base64Encoded', False):
                                import base64
                                response_text = base64.b64decode(response_body['body']).decode('utf-8')
                            else:
                                response_text = response_body['body']

                            target_response = json.loads(response_text)
                            break
                        except Exception:
                            continue
                except:
                    continue

            if not target_response:
                try:
                    page_source = self.driver.page_source
                    render_data_match = re.search(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>',
                                                  page_source)
                    if render_data_match:
                        render_data_str = render_data_match.group(1)
                        render_data = json.loads(unquote(render_data_str))
                        target_response = render_data
                except Exception:
                    pass

            if not target_response:
                return None

            aweme_detail = None
            if 'aweme_detail' in target_response:
                aweme_detail = target_response.get('aweme_detail', {})
            elif 'aweme_details' in target_response and target_response['aweme_details']:
                aweme_detail = target_response['aweme_details'][0]
            elif 'item_list' in target_response and target_response['item_list']:
                aweme_detail = target_response['item_list'][0]
            elif 'video' in target_response:
                aweme_detail = {'video': target_response}

            if not aweme_detail:
                return None

            video_info = aweme_detail.get('video', {})
            download_url_list = []
            play_url_list = []

            url_fields = ['download_addr', 'play_addr', 'play_addr_h264', 'play_addr_265']
            for field in url_fields:
                if field in video_info and 'url_list' in video_info[field]:
                    if field.startswith('download'):
                        download_url_list = video_info[field]['url_list']
                    else:
                        play_url_list = video_info[field]['url_list']

            final_url = download_url_list[0] if download_url_list else (play_url_list[0] if play_url_list else None)
            if not final_url:
                return None

            result = {
                "original_url": video_page_url,
                "video_id": video_id,
                "standard_url": standard_url,
                "author_nickname": aweme_detail.get('author', {}).get('nickname', '未知'),
                "video_title": aweme_detail.get('desc', '无标题').replace('/', '_').replace('\\', '_'),
                "download_url": final_url,
                "all_urls": {
                    "download_urls": download_url_list,
                    "play_urls": play_url_list
                }
            }
            return result
        except Exception:
            return None
        finally:
            if self.driver:
                self.driver.quit()

    def download_video(self, video_info, save_dir):
        if not video_info or 'download_url' not in video_info:
            return False

        video_url = unquote(video_info['download_url'])
        video_id = video_info['video_id']
        video_title = video_info.get('video_title', video_id)

        safe_title = re.sub(r'[\\/:*?"<>|]', '_', video_title)
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{save_dir}/{safe_title}_{video_id}.mp4"

        print("\n开始下载抖音视频...")

        download_session = requests.Session()
        download_session.headers.update(self.download_headers)
        download_session.keep_alive = False
        download_session.verify = False

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = download_session.get(
                    video_url,
                    stream=True,
                    timeout=60,
                    verify=False
                )

                if response.status_code == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=16384):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    print(f"\r下载进度：{percent:.1f}%", end='', flush=True)

                    if self._verify_download(filename, downloaded):
                        print(f"\n抖音视频下载成功：{filename}")
                        return True
                    else:
                        if os.path.exists(filename):
                            os.remove(filename)
                        time.sleep(2)

                elif response.status_code == 403:
                    print("\n403拒绝访问：Cookie过期或URL需要登录")
                    return False
                elif response.status_code == 404:
                    print("\n404 URL过期：需重新抓取")
                    return False
                else:
                    print(f"\n下载失败，状态码：{response.status_code}")

            except Exception:
                pass

            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)

        print("抖音视频下载失败")
        return False

    def _verify_download(self, filename, expected_size):
        if not os.path.exists(filename):
            return False

        actual_size = os.path.getsize(filename)
        if expected_size > 0 and abs(actual_size - expected_size) > 1024:
            return False
        if actual_size < 10 * 1024:
            return False
        return True

    def download_from_url(self, url, save_dir):
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        video_info = self.get_video_info(url)
        if not video_info:
            return False

        success = self.download_video(video_info, save_dir)
        return success


# B站下载模块
def resolve_bilibili_short_url(short_url):
    try:
        resolve_headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        response = requests.get(short_url, headers=resolve_headers, allow_redirects=False, timeout=10)
        if 'Location' in response.headers:
            return response.headers['Location']
        elif response.status_code in [301, 302, 307]:
            return resolve_bilibili_short_url(response.headers.get('Location', short_url))
        else:
            html = etree.HTML(response.text)
            redirect_script = html.xpath('//script[contains(text(), "window.location")]/text()')
            if redirect_script:
                url_match = re.search(r'window\.location\.href\s*=\s*["\'](.*?)["\']', redirect_script[0])
                if url_match:
                    return url_match.group(1)

        return short_url
    except Exception:
        return short_url


def get_bilibili_play_info(url):
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        'Referer': 'https://www.bilibili.com/',
        'Origin': 'https://www.bilibili.com'
    }
    session = requests.Session()
    session.headers.update(headers)
    response = session.get(url)

    play_info_match = re.search(r'window\.__playinfo__\s*=\s*({.*?})</script>', response.text, re.DOTALL)
    if not play_info_match:
        return None, None, None

    play_info = json.loads(play_info_match.group(1))
    html = etree.HTML(response.text)
    title_elements = html.xpath('//h1[@class="video-title"]/text()')
    if title_elements:
        original_title = title_elements[0].strip()
    else:
        title_elements = html.xpath('//title/text()')
        original_title = title_elements[0].strip() if title_elements else "未命名视频"

    return play_info, original_title, session


def download_bilibili_file(url, filename, session, chunk_size=8192):
    try:
        headers_with_referer = {
            **session.headers,
            'Referer': 'https://www.bilibili.com/'
        }

        response = session.get(url, headers=headers_with_referer, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        with open(filename, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = (downloaded / total_size) * 100
                        print(f"\r下载中... {progress:.1f}%", end='')
        print(f"\nB站文件下载完成：{filename}")
        return True
    except Exception:
        print(f"\nB站文件下载失败 {filename}")
        return False


def get_bilibili_best_quality_url(play_info):
    try:
        data = play_info.get('data', {})
        if 'dash' in data:
            video_list = data['dash'].get('video', [])
            audio_list = data['dash'].get('audio', [])
            if video_list and audio_list:
                video_list.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)
                audio_list.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)
                video_url = video_list[0].get('baseUrl', '')
                audio_url = audio_list[0].get('baseUrl', '')
                if not video_url and 'backupUrl' in video_list[0]:
                    video_url = video_list[0]['backupUrl'][0] if video_list[0]['backupUrl'] else ''
                if not audio_url and 'backupUrl' in audio_list[0]:
                    audio_url = audio_list[0]['backupUrl'][0] if audio_list[0]['backupUrl'] else ''
                return video_url, audio_url

        if 'durl' in data:
            durls = data['durl']
            if durls:
                video_url = durls[0].get('url', '')
                return video_url, None

        return None, None
    except Exception:
        return None, None


def merge_bilibili_video_audio(video_path, audio_path, output_path):
    try:
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-y',
            '-loglevel', 'error',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
                return True
            else:
                print("B站合并后的文件无效或为空")
                return False
        else:
            print("B站音视频合并失败")
            return False
    except FileNotFoundError:
        print("未找到ffmpeg！请先安装并配置环境变量")
        return False
    except Exception:
        print("B站合并过程出错")
        return False


def bilibili_download_from_url(url, save_dir):
    if 'b23.tv' in url:
        url = resolve_bilibili_short_url(url)
    play_info, title, session = get_bilibili_play_info(url)
    if not play_info or not title:
        return False
    video_url, audio_url = get_bilibili_best_quality_url(play_info)
    if not video_url:
        return False

    temp_path = os.path.join(save_dir, "temp")
    create_dir(save_dir)
    create_dir(temp_path)

    safe_title = safe_filename(title)
    temp_video_file = os.path.join(temp_path, f"{safe_title}_video.mp4")
    temp_audio_file = os.path.join(temp_path, f"{safe_title}_audio.mp3")
    final_video_file = os.path.join(save_dir, f"{safe_title}.mp4")

    print("开始下载B站视频...")
    video_download_ok = download_bilibili_file(video_url, temp_video_file, session)

    audio_download_ok = True
    if audio_url:
        print("开始下载B站音频...")
        audio_download_ok = download_bilibili_file(audio_url, temp_audio_file, session)

    if video_download_ok:
        if audio_url and audio_download_ok:
            merge_ok = merge_bilibili_video_audio(temp_video_file, temp_audio_file, final_video_file)
            if merge_ok:
                if os.path.exists(temp_video_file):
                    os.remove(temp_video_file)
                if os.path.exists(temp_audio_file):
                    os.remove(temp_audio_file)
                if os.path.exists(temp_path) and not os.listdir(temp_path):
                    os.rmdir(temp_path)
            else:
                print("B站音视频合并失败，保留分离的音视频文件")
        else:
            shutil.move(temp_video_file, final_video_file)
            print(f"\nB站视频已保存到: {final_video_file}")
            if os.path.exists(temp_path) and not os.listdir(temp_path):
                os.rmdir(temp_path)

    print("B站视频下载完成！")
    return True

# 主调度函数（修改快手调用部分）
def download_video_by_url(url):
    platform = identify_platform(url)
    if not platform:
        print("无法识别URL的平台")
        return False
    platform_dir = create_dir(os.path.join(ROOT_DOWNLOAD_DIR, platform))
    try:
        if platform == "xiaohongshu":
            downloader = XiaohongshuDownloader()
            return downloader.download_from_url(url, platform_dir)
        elif platform == "weibo":
            return weibo_download_from_url(url, platform_dir)
        elif platform == "kuaishou":
            # 重要：改为headless=False显示浏览器
            downloader = KuaishouVideoDownloader(save_dir=platform_dir, headless=False)
            return downloader.download_from_url(url, platform_dir)
        elif platform == "douyin":
            downloader = DouyinVideoCrawlerAndDownloader()
            return downloader.download_from_url(url, platform_dir)
        elif platform == "bilibili":
            return bilibili_download_from_url(url, platform_dir)
        else:
            print(f"未实现{platform}平台的下载逻辑")
            return False
    except Exception as e:
        print(f"{platform}下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 运行入口
if __name__ == "__main__":
    print("多平台视频下载工具 (支持：抖音/快手/B站/小红书/微博)")
    target_url = 'https://www.kuaishou.com/short-video/3xqjuqwzhn3jzbq?authorId=3xf9iwgt9jm74ig&streamSource=brilliant&hotChannelId=00&area=brilliantxxcarefully'
    if not target_url:
        print("URL不能为空！")
    else:
        success = download_video_by_url(target_url)
        if success:
            print("\n下载成功")
        else:
            print("\n下载失败")