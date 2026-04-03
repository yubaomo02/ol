import os
import re
import asyncio
import httpx
import time
from collections import OrderedDict

# --- 配置区 ---
# 1. 权限与路径
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "yubaomo02"
REPO_NAME = "ol"
FOLDER_PATH = "zubo"

# 2. 测速参数
TIMEOUT = 5.0          # 每一个链接最多等待5秒
MIN_SPEED_MB = 0.5     # 门槛：低于 0.5MB/s 的不要
MAX_CONCURRENT = 40    # 并发数：建议 30-50，太高容易被 GitHub 防火墙拦截
CHUNK_SIZE = 1024 * 512 # 测速数据量：512KB (足够判断是否流畅)

# 3. 分类逻辑 (保持你提供的顺序)
CATEGORIES = OrderedDict([
    ("央视频道", ["CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K", "兵器科技", "风云音乐", "风云足球", "风云剧场", "怀旧剧场", "第一剧场", "女性时尚", "世界地理", "央视台球", "高尔夫网球", "央视文化精品", "卫生健康", "电视指南"]),
    ("卫视频道", ["湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "广西卫视", "东南卫视", "海南卫视", "河北卫视", "河南卫视", "湖北卫视", "江西卫视", "四川卫视", "重庆卫视", "贵州卫视", "云南卫视", "天津卫视", "安徽卫视", "山东卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视", "内蒙古卫视", "宁夏卫视", "山西卫视", "陕西卫视", "甘肃卫视", "青海卫视", "新疆卫视", "西藏卫视", "三沙卫视", "山东教育卫视", "中国教育1台", "中国教育2台", "中国教育3台", "中国教育4台", "早期教育"]),
    ("数字频道", ["CHC动作电影", "CHC家庭影院", "CHC影迷电影", "淘电影", "淘精彩", "淘剧场", "淘4K", "淘娱乐", "淘BABY", "淘萌宠", "重温经典", "星空卫视", "ChannelV", "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "求索纪录", "求索科学", "求索生活", "求索动物", "纪实人文", "金鹰纪实", "纪实科教", "睛彩青少", "睛彩竞技", "睛彩篮球", "睛彩广场舞", "魅力足球", "五星体育", "乐游", "生活时尚", "都市剧场", "欢笑剧场", "游戏风云", "金色学堂", "动漫秀场", "新动漫", "卡酷少儿", "金鹰卡通", "优漫卡通", "哈哈炫动", "嘉佳卡通","中国交通", "中国天气", "华数4K", "华数星影", "华数动作影院", "华数喜剧影院", "华数家庭影院", "华数经典电影", "华数热播剧场", "华数碟战剧场","华数军旅剧场", "华数城市剧场", "华数武侠剧场", "华数古装剧场", "华数魅力时尚", "华数少儿动画", "华数动画"]),
    ("4K频道", ["东方卫视4K","浙江卫视4K","江苏卫视4K","北京卫视4K","湖南卫视4K","广东卫视4K","四川卫视4K","深圳卫视4K","山东卫视4K","欢笑剧场4K"]),
    ("湖北", ["湖北公共新闻", "湖北经视频道", "湖北综合频道", "湖北垄上频道", "湖北影视频道", "湖北生活频道", "湖北教育频道", "武汉新闻综合", "武汉电视剧", "武汉科技生活","武汉文体频道", "武汉教育频道", "阳新综合", "房县综合", "蔡甸综合"]),
    ("安徽", ["安徽经济生活","安徽公共频道","安徽国际频道","安徽农业科教","安徽影视频道","安徽综艺体育","安庆经济生活","安庆新闻综合"])
])

# --- 工具函数 ---

def clean_channel_name(name):
    """去除干扰字符进行逻辑匹配"""
    return re.sub(r'\(.*?\)|\[.*?\]|HD|高清|标清|超清|频道', '', name).strip()

def clean_suffix(suffix):
    """移除后缀末尾的 IP 和 端口 ID"""
    if not suffix: return "未知"
    return re.sub(r'_[0-9\._]+$', '', suffix).strip()

async def test_speed(client, channel_info, idx, total):
    """核心测速函数"""
    url = channel_info['url']
    name = channel_info['name']
    suffix = channel_info['suffix']
    
    try:
        start_time = time.time()
        # 使用 stream 模式，只下载一小块数据
        async with client.stream("GET", url, timeout=TIMEOUT) as response:
            if response.status_code != 200:
                return None
            
            content_length = 0
            async for chunk in response.aiter_bytes(chunk_size=1024):
                content_length += len(chunk)
                # 达到 512KB 或者 超过超时时间就停止
                if content_length >= CHUNK_SIZE or (time.time() - start_time) > TIMEOUT:
                    break
            
            duration = time.time() - start_time
            speed_mb = (content_length / 1024 / 1024) / duration if duration > 0 else 0
            
            if speed_mb >= MIN_SPEED_MB:
                print(f"[{idx}/{total}] ✅ 通过 | {name} | {suffix} | {speed_mb:.2f} MB/s", flush=True)
                return channel_info
            else:
                print(f"[{idx}/{total}] ⚠️  丢弃 | {name} | {speed_mb:.2f} MB/s (太慢)", flush=True)
    except:
        # 超时或挂掉的源不打印，保持日志干净
        pass
    return None

async def main():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, verify=False) as client:
        # 1. 获取目录下的所有 m3u
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FOLDER_PATH}"
        print(f"🔍 正在连接 GitHub API 获取文件列表...", flush=True)
        resp = await client.get(api_url)
        if resp.status_code != 200:
            print(f"❌ 无法读取目录: {resp.status_code}")
            return
        
        m3u_urls = [f['download_url'] for f in resp.json() if f['name'].endswith('.m3u')]
        print(f"获取到 {len(m3u_urls)} 个 M3U 文件，开始解析内容...", flush=True)

        # 2. 汇总所有频道
        all_channels = []
        for m3u_url in m3u_urls:
            r = await client.get(m3u_url)
            lines = r.text.split('\n')
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF:"):
                    # 提取后缀和名称
                    suffix = "未知"
                    g_match = re.search(r'group-title="(.*?)"', lines[i])
                    if g_match:
                        suffix = clean_suffix(g_match.group(1))
                    
                    name = lines[i].split(',')[-1].strip()
                    if i + 1 < len(lines) and lines[i+1].startswith("http"):
                        all_channels.append({
                            "name": name,
                            "url": lines[i+1].strip(),
                            "suffix": suffix,
                            "pure_name": clean_channel_name(name)
                        })

        # 3. 筛选在分类表中的频道
        valid_set = set([n for sub in CATEGORIES.values() for n in sub])
        to_test = [ch for ch in all_channels if ch['pure_name'] in valid_set]
        total = len(to_test)
        
        print(f"📊 待测频道总数: {total} (已过滤不在分类表中的频道)", flush=True)

        # 4. 并发测速
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        async def sem_task(ch, idx):
            async with semaphore:
                return await test_speed(client, ch, idx, total)

        tasks = [sem_task(ch, i+1) for i, ch in enumerate(to_test)]
        results = await asyncio.gather(*tasks)

        # 5. 格式化输出结果
        final_output = OrderedDict({cat: [] for cat in CATEGORIES})
        for res in results:
            if res:
                for cat, names in CATEGORIES.items():
                    if res['pure_name'] in names:
                        line = f"{res['name']},{res['url']}${res['suffix']}"
                        final_output[cat].append(line)
                        break

        # 6. 保存为 TXT 格式
        with open("zubo_live.txt", "w", encoding="utf-8") as f:
            for cat, lines in final_output.items():
                if lines:
                    f.write(f"{cat},#genre#\n")
                    # 去重并排序
                    for l in sorted(list(set(lines))):
                        f.write(l + "\n")
                    f.write("\n")
        
        print(f"🚀 任务执行完毕！zubo_live.txt 已生成。", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
