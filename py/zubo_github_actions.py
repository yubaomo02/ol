import os
import re
import asyncio
import httpx
import time
from collections import OrderedDict

# --- 配置区 ---
# 1. 自动从 GitHub Secrets 获取 Token (需在 Action 中配置)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "yubaomo02"
REPO_NAME = "ol"
FOLDER_PATH = "zubo"

# 2. 测速配置
TIMEOUT = 5.0      # 单个链接超时时间
MIN_SPEED_MB = 0.5 # 播放门槛：0.5MB/s
MAX_CONCURRENT = 50 # 最大并发数 (Actions 环境建议 50-100)
CHUNK_SIZE = 1024 * 512 # 测速下载 512KB 即可判断速度

# 分类逻辑
CATEGORIES = OrderedDict([
    ("央视频道", ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K", "兵器科技", "风云音乐", "风云足球", "风云剧场", "怀旧剧场", "第一剧场", "女性时尚", "世界地理", "央视台球", "高尔夫网球", "央视文化精品", "卫生健康", "电视指南"]),
    ("卫视频道", ["湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "广西卫视", "东南卫视", "海南卫视", "河北卫视", "河南卫视", "湖北卫视", "江西卫视", "四川卫视", "重庆卫视", "贵州卫视", "云南卫视", "天津卫视", "安徽卫视", "山东卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视", "内蒙古卫视", "宁夏卫视", "山西卫视", "陕西卫视", "甘肃卫视", "青海卫视", "新疆卫视", "西藏卫视", "三沙卫视", "山东教育卫视", "中国教育1台", "中国教育2台", "中国教育3台", "中国教育4台", "早期教育"]),
    ("数字频道", ["CHC动作电影", "CHC家庭影院", "CHC影迷电影", "淘电影", "淘精彩", "淘剧场", "淘4K", "淘娱乐", "淘BABY", "淘萌宠", "重温经典", "星空卫视", "ChannelV", "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "求索纪录", "求索科学", "求索生活", "求索动物", "纪实人文", "金鹰纪实", "纪实科教", "睛彩青少", "睛彩竞技", "睛彩篮球", "睛彩广场舞", "魅力足球", "五星体育", "乐游", "生活时尚", "都市剧场", "欢笑剧场", "游戏风云", "金色学堂", "动漫秀场", "新动漫", "卡酷少儿", "金鹰卡通", "优漫卡通", "哈哈炫动", "嘉佳卡通","中国交通", "中国天气", "华数4K", "华数星影", "华数动作影院", "华数喜剧影院", "华数家庭影院", "华数经典电影", "华数热播剧场", "华数碟战剧场","华数军旅剧场", "华数城市剧场", "华数武侠剧场", "华数古装剧场", "华数魅力时尚", "华数少儿动画", "华数动画"]),
    ("4K频道", ["东方卫视4K","浙江卫视4K","江苏卫视4K","北京卫视4K","湖南卫视4K","广东卫视4K","四川卫视4K","深圳卫视4K","山东卫视4K","欢笑剧场4K"]),
    ("湖北", ["湖北公共新闻", "湖北经视频道", "湖北综合频道", "湖北垄上频道", "湖北影视频道", "湖北生活频道", "湖北教育频道", "武汉新闻综合", "武汉电视剧", "武汉科技生活","武汉文体频道", "武汉教育频道", "阳新综合", "房县综合", "蔡甸综合"]),
    ("安徽", ["安徽经济生活","安徽公共频道","安徽国际频道","安徽农业科教","安徽影视频道","安徽综艺体育","安庆经济生活","安庆新闻综合"])
])

def clean_channel_name(name):
    return re.sub(r'\(.*?\)|\[.*?\]|HD|高清|标清|超清|频道', '', name).strip()

def clean_suffix(suffix):
    # 去除北京联通_114.243.96.9_8888 这种格式的尾部
    return re.sub(r'_[0-9\._]+$', '', suffix).strip()

async def test_speed(client, channel_info):
    """异步测速函数"""
    url = channel_info['url']
    try:
        start_time = time.time()
        async with client.stream("GET", url, timeout=TIMEOUT) as response:
            if response.status_code != 200: return None
            
            content_length = 0
            async for chunk in response.aiter_bytes(chunk_size=1024):
                content_length += len(chunk)
                if content_length >= CHUNK_SIZE or (time.time() - start_time) > TIMEOUT:
                    break
            
            duration = time.time() - start_time
            speed_mb = (content_length / 1024 / 1024) / duration if duration > 0 else 0
            
            if speed_mb >= MIN_SPEED_MB:
                return channel_info
    except:
        pass
    return None

async def main():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # 1. 获取文件列表
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FOLDER_PATH}"
        resp = await client.get(api_url)
        if resp.status_code != 200:
            print(f"无法访问 GitHub API: {resp.status_code}")
            return
        
        m3u_files = [f['download_url'] for f in resp.json() if f['name'].endswith('.m3u')]
        print(f"找到 {len(m3u_files)} 个 M3U 文件，正在解析...")

        # 2. 解析所有 M3U 内容
        all_channels = []
        for url in m3u_files:
            r = await client.get(url)
            lines = r.text.split('\n')
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF:"):
                    suffix = ""
                    group_match = re.search(r'group-title="(.*?)"', lines[i])
                    if group_match:
                        suffix = clean_suffix(group_match.group(1))
                    
                    name = lines[i].split(',')[-1].strip()
                    if i + 1 < len(lines) and lines[i+1].startswith("http"):
                        all_channels.append({
                            "name": name, 
                            "url": lines[i+1].strip(), 
                            "suffix": suffix,
                            "pure_name": clean_channel_name(name)
                        })

        # 3. 过滤出分类名单内的频道
        to_test = []
        valid_names = set([name for sublist in CATEGORIES.values() for name in sublist])
        for ch in all_channels:
            if ch['pure_name'] in valid_names:
                to_test.append(ch)

        print(f"筛选出 {len(to_test)} 条分类频道，开始并发测速 (并发数:{MAX_CONCURRENT})...")

        # 4. 并发测速
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        async def sem_test(ch):
            async with semaphore:
                return await test_speed(client, ch)

        tasks = [sem_test(ch) for ch in to_test]
        results = await asyncio.gather(*tasks)
        
        # 5. 整理结果并去重
        final_output = OrderedDict({cat: [] for cat in CATEGORIES})
        for res in results:
            if res:
                for cat, names in CATEGORIES.items():
                    if res['pure_name'] in names:
                        line = f"{res['name']},{res['url']}${res['suffix']}"
                        final_output[cat].append(line)
                        break

        # 6. 写入文件
        with open("zubo_live.txt", "w", encoding="utf-8") as f:
            for cat, lines in final_output.items():
                if lines:
                    f.write(f"{cat},#genre#\n")
                    for l in sorted(list(set(lines))): # 去重并简单排序
                        f.write(l + "\n")
                    f.write("\n")
        
        print("✅ 任务完成，生成 zubo_live.txt")

if __name__ == "__main__":
    asyncio.run(main())
