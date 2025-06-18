"""
简化的测试爬虫
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from loguru import logger
import json
from pathlib import Path


class SimpleCrawler:
    """简化的测试爬虫"""
    
    def __init__(self):
        self.base_url = "https://flk.npc.gov.cn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
    async def test_connection(self):
        """测试网站连接"""
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            try:
                # 测试主页
                logger.info(f"测试访问主页: {self.base_url}")
                response = await client.get(self.base_url, headers=self.headers)
                logger.info(f"主页状态码: {response.status_code}")
                
                # 保存响应内容用于分析
                Path("data/test").mkdir(parents=True, exist_ok=True)
                with open("data/test/homepage.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                
                # 分析页面结构
                soup = BeautifulSoup(response.text, 'html.parser')
                logger.info(f"页面标题: {soup.title.string if soup.title else 'N/A'}")
                
                # 查找搜索相关的元素
                search_forms = soup.find_all('form')
                logger.info(f"找到 {len(search_forms)} 个表单")
                
                # 查找可能的API端点
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and ('api' in script.string or 'search' in script.string):
                        logger.info("找到可能的API相关脚本")
                        
                return True
                
            except Exception as e:
                logger.error(f"连接测试失败: {str(e)}")
                return False
                
    async def search_by_url(self, law_name: str):
        """通过URL参数搜索"""
        search_urls = [
            f"{self.base_url}/search?q={law_name}",
            f"{self.base_url}/list.html?keyword={law_name}",
            f"{self.base_url}/fl.html?keyword={law_name}",
        ]
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            for url in search_urls:
                try:
                    logger.info(f"尝试搜索URL: {url}")
                    response = await client.get(url, headers=self.headers)
                    
                    if response.status_code == 200:
                        logger.info(f"成功访问: {url}")
                        
                        # 保存响应
                        filename = f"data/test/search_{law_name.replace(' ', '_')}.html"
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(response.text)
                            
                        # 简单解析
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # 查找可能的法律列表
                        tables = soup.find_all('table')
                        if tables:
                            logger.info(f"找到 {len(tables)} 个表格")
                            
                        # 查找链接
                        links = soup.find_all('a', href=True)
                        law_links = [link for link in links if law_name in link.text or '反洗钱' in link.text]
                        
                        if law_links:
                            logger.info(f"找到 {len(law_links)} 个相关链接")
                            for link in law_links[:3]:  # 只显示前3个
                                logger.info(f"  - {link.text.strip()}: {link['href']}")
                                
                        return response.text
                        
                except Exception as e:
                    logger.error(f"搜索失败 {url}: {str(e)}")
                    
        return None
        
    async def get_law_detail_by_url(self, detail_url: str):
        """获取法律详情"""
        if not detail_url.startswith('http'):
            detail_url = self.base_url + detail_url
            
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            try:
                logger.info(f"获取法律详情: {detail_url}")
                response = await client.get(detail_url, headers=self.headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 提取基本信息
                    title = soup.find('h1') or soup.find('h2') or soup.find('title')
                    title_text = title.text.strip() if title else "未知标题"
                    
                    # 查找内容区域
                    content_div = soup.find('div', class_='content') or soup.find('div', id='content')
                    content_text = content_div.text.strip() if content_div else response.text
                    
                    logger.info(f"获取到法律: {title_text}")
                    logger.info(f"内容长度: {len(content_text)}")
                    
                    return {
                        "title": title_text,
                        "content": content_text,
                        "url": detail_url
                    }
                    
            except Exception as e:
                logger.error(f"获取详情失败: {str(e)}")
                
        return None


async def test_simple_crawler():
    """测试简化爬虫"""
    crawler = SimpleCrawler()
    
    # 1. 测试连接
    logger.info("=== 测试网站连接 ===")
    connected = await crawler.test_connection()
    
    if connected:
        # 2. 测试搜索
        logger.info("\n=== 测试搜索功能 ===")
        await crawler.search_by_url("反洗钱法")
        
        # 3. 测试已知的法律详情页
        logger.info("\n=== 测试法律详情页 ===")
        # 这是一个示例URL，可能需要根据实际情况调整
        test_urls = [
            "/detail.html?sysId=1",
            "/fl/detail.html?id=1"
        ]
        
        for url in test_urls:
            detail = await crawler.get_law_detail_by_url(url)
            if detail:
                break


if __name__ == "__main__":
    asyncio.run(test_simple_crawler()) 