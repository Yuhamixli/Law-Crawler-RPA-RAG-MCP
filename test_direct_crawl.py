"""
直接测试法律详情页爬取
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from loguru import logger
import json
from pathlib import Path


async def test_known_laws():
    """测试一些已知的法律详情页"""
    
    # 从主页找到的一些法律详情页ID
    known_laws = [
        {
            "name": "中华人民共和国监察法",
            "id": "ZmY4MDgxODE5NDQwNjk3MjAxOTQ5NjBkY2VhMzQ1YTI%3D"
        },
        {
            "name": "中华人民共和国增值税法", 
            "id": "ZmY4MDgxODE5MjdiMDgzYjAxOTNmZDY1YTBlYjAyY2I%3D"
        },
        {
            "name": "中华人民共和国科学技术普及法",
            "id": "ZmY4MDgxODE5MjdiMDgzYjAxOTNmZGE0YmVhZDAyZWU%3D"
        }
    ]
    
    base_url = "https://flk.npc.gov.cn/detail2.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    
    Path("data/test_laws").mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient(timeout=30) as client:
        for law in known_laws:
            try:
                url = f"{base_url}?{law['id']}"
                logger.info(f"测试爬取: {law['name']}")
                logger.info(f"URL: {url}")
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    # 保存HTML
                    html_file = f"data/test_laws/{law['name']}.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    
                    # 解析内容
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找标题
                    title = None
                    for tag in ['h1', 'h2', 'div']:
                        elem = soup.find(tag, class_='title')
                        if elem:
                            title = elem.text.strip()
                            break
                    
                    if not title:
                        # 尝试从title标签获取
                        title_tag = soup.find('title')
                        if title_tag:
                            title = title_tag.text.strip()
                    
                    # 查找内容
                    content = None
                    content_elem = soup.find('div', class_='content')
                    if content_elem:
                        content = content_elem.get_text(separator='\n', strip=True)
                    else:
                        # 尝试其他方式
                        main_elem = soup.find('div', class_='main') or soup.find('div', id='main')
                        if main_elem:
                            content = main_elem.get_text(separator='\n', strip=True)
                    
                    logger.info(f"标题: {title}")
                    logger.info(f"内容长度: {len(content) if content else 0}")
                    
                    # 保存解析结果
                    result = {
                        "name": law['name'],
                        "title": title,
                        "content_length": len(content) if content else 0,
                        "content_preview": content[:500] if content else "无内容"
                    }
                    
                    json_file = f"data/test_laws/{law['name']}.json"
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    
                    logger.success(f"成功爬取: {law['name']}")
                else:
                    logger.error(f"请求失败: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"爬取失败: {law['name']}, 错误: {str(e)}")
            
            await asyncio.sleep(2)  # 延迟


async def search_law_on_site():
    """测试网站的搜索功能"""
    search_term = "反洗钱法"
    
    # 可能的搜索API端点
    search_urls = [
        f"https://flk.npc.gov.cn/api/search?keyword={search_term}",
        f"https://flk.npc.gov.cn/search?q={search_term}",
        f"https://flk.npc.gov.cn/list.html?keyword={search_term}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        for url in search_urls:
            try:
                logger.info(f"尝试搜索: {url}")
                response = await client.get(url, headers=headers)
                
                logger.info(f"状态码: {response.status_code}")
                logger.info(f"内容类型: {response.headers.get('content-type', 'unknown')}")
                
                if response.status_code == 200:
                    # 检查是否是JSON响应
                    if 'json' in response.headers.get('content-type', ''):
                        data = response.json()
                        logger.info(f"JSON响应: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
                    else:
                        # HTML响应
                        logger.info(f"HTML响应长度: {len(response.text)}")
                        
                        # 检查是否包含搜索结果
                        if search_term in response.text:
                            logger.success(f"找到包含'{search_term}'的内容")
                            
                            # 保存响应
                            with open(f"data/test_laws/search_result_{search_term}.html", 'w', encoding='utf-8') as f:
                                f.write(response.text)
                                
            except Exception as e:
                logger.error(f"搜索失败: {url}, 错误: {str(e)}")
                
            await asyncio.sleep(1)


async def main():
    """主函数"""
    print("=== 法律详情页测试 ===\n")
    
    # 1. 测试已知的法律详情页
    await test_known_laws()
    
    print("\n=== 搜索功能测试 ===\n")
    
    # 2. 测试搜索功能
    await search_law_on_site()


if __name__ == "__main__":
    asyncio.run(main()) 