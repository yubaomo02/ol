import os
import re
import asyncio
import httpx
from collections import OrderedDict

# --- 配置区 ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "yubaomo02"
REPO_NAME = "ol"
FOLDER_PATH = "zubo"

TIMEOUT = 5.0 
MAX_CONCURRENT = 50 

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
    if not suffix: return "未知"
    return re.sub(r'_[0-9\._]+$', '', suffix).strip()

async def check_link(client, ch, idx, total):
    try:
        # 改用 GET 并只读取极小数据，兼容性比 HEAD 更好
        async with client.stream("GET", ch['url'], timeout=TIMEOUT) as resp:
            if resp.status_code == 200:
                return ch
    except:
        pass
    return None

async def main():
    # 确保在根目录生成文件
    os.chdir(os.path.join(os.getcwd(), '..')) if os.path.basename(os.getcwd()) == 'py' else None
    
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, verify=False) as client:
        # 1. 获取文件列表
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FOLDER_PATH}"
        resp = await client.get(api_url)
        if resp.status_code != 200:
            print(f"❌ API 请求失败: {resp.status_code}")
            return
        
        m3u_files = [f for f in resp.json() if f['name'].endswith('.m3u')]
        print(f"📂 找到 {len(m3u_files)} 个 M3U 文件")

        # 2. 解析
        all_channels = []
        for f_info in m3u_files:
            r = await client.get(f_info['download_url'])
            lines = [l.strip() for l in r.text.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                if line.startswith("#EXTINF:"):
                    suffix = "未知"
                    g_match = re.search(r'group-title="(.*?)"', line)
                    if g_match: suffix = clean_suffix(g_match.group(1))
                    name = line.split(',')[-1].strip()
                    if i + 1 < len(lines):
                        u = lines[i+1]
                        if u.startswith("http"):
                            all_channels.append({"name": name, "url": u, "suffix": suffix, "pure": clean_channel_name(name)})
        
        print(f"总计解析到 {len(all_channels)} 条原始频道")

        # 3. 过滤
        valid_names = set([n for sub in CATEGORIES.values() for n in sub])
        to_check = [ch for ch in all_channels if ch['pure'] in valid_names]
        print(f"🎯 匹配到分类关键词的频道数: {len(to_check)}")

        # 4. 存活检测
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        async def task(ch, i):
            async with sem: return await check_link(client, ch, i, len(to_check))
        
        results = await asyncio.gather(*(task(ch, i+1) for i, ch in enumerate(to_check)))
        valid_results = [r for r in results if r]
        print(f"✅ 存活检测完成，有效频道: {len(valid_results)}")

        # 5. 整理数据
        final_data = OrderedDict({cat: [] for cat in CATEGORIES})
        for r in valid_results:
            for cat, names in CATEGORIES.items():
                if r['pure'] in names:
                    final_data[cat].append(r)
                    break

        # --- 输出 TXT ---
        txt_content = []
        for cat, channels in final_data.items():
            if channels:
                txt_content.append(f"{cat},#genre#")
                unique = list({f"{c['name']},{c['url']}${c['suffix']}": None for c in channels}.keys())
                txt_content.extend(sorted(unique))
                txt_content.append("")
        
        with open("zubo_live.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(txt_content))

        # --- 输出 M3U ---
        m3u_content = ["#EXTM3U"]
        for cat, channels in final_data.items():
            for c in channels:
                m3u_content.append(f'#EXTINF:-1 group-title="{cat}",{c["name"]}')
                m3u_content.append(c["url"])
        
        with open("zubo_live.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

    print(f"💾 文件写入成功：zubo_live.txt ({len(txt_content)}行), zubo_live.m3u ({len(m3u_content)}行)")

if __name__ == "__main__":
    asyncio.run(main())
