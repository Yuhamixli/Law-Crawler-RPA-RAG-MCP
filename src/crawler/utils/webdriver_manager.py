#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebDriver管理器 - 预热和复用Chrome WebDriver实例
"""

import asyncio
import random
import time
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger


class WebDriverManager:
    """WebDriver管理器 - 单例模式"""
    
    _instance = None
    _drivers = {}  # 存储不同类型的driver实例
    _last_used = {}  # 记录最后使用时间
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = logger
            self._max_idle_time = 300  # 5分钟闲置时间后关闭
            self._cleanup_interval = 60  # 每分钟检查一次清理
            self._last_cleanup = time.time()
            self._initialized = True
    
    async def get_driver(self, driver_type: str = "default", **options) -> Optional[webdriver.Chrome]:
        """获取WebDriver实例，支持复用"""
        try:
            # 检查是否需要清理闲置的driver
            await self._cleanup_idle_drivers()
            
            # 如果已存在可用的driver，直接返回
            if driver_type in self._drivers:
                driver = self._drivers[driver_type]
                if self._is_driver_alive(driver):
                    self._last_used[driver_type] = time.time()
                    self.logger.debug(f"复用WebDriver: {driver_type}")
                    return driver
                else:
                    # Driver已死，清理并重新创建
                    self.logger.warning(f"WebDriver {driver_type} 已失效，重新创建")
                    await self._close_driver(driver_type)
            
            # 创建新的driver
            driver = await self._create_driver(**options)
            if driver:
                self._drivers[driver_type] = driver
                self._last_used[driver_type] = time.time()
                self.logger.success(f"WebDriver {driver_type} 创建成功")
                return driver
            
        except Exception as e:
            self.logger.error(f"获取WebDriver失败: {e}")
        
        return None
    
    async def _create_driver(self, **options) -> Optional[webdriver.Chrome]:
        """创建新的Chrome WebDriver"""
        try:
            chrome_options = Options()
            
            # 基础反检测配置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 性能优化配置
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-default-apps')
            
            # 随机窗口大小
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            chrome_options.add_argument(f'--window-size={width},{height}')
            
            # 随机User-Agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
            ]
            user_agent = random.choice(user_agents)
            chrome_options.add_argument(f'--user-agent={user_agent}')
            
            # 禁用图片和媒体加载以提升速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.media_stream": 2,
                "profile.managed_default_content_settings.media_stream": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # 应用自定义选项
            for key, value in options.items():
                if key == 'proxy' and value:
                    chrome_options.add_argument(f'--proxy-server={value}')
                elif key == 'user_agent' and value:
                    chrome_options.add_argument(f'--user-agent={value}')
                elif key == 'window_size' and value:
                    chrome_options.add_argument(f'--window-size={value}')
            
            # 创建驱动
            try:
                # 尝试使用系统PATH中的ChromeDriver
                driver = webdriver.Chrome(options=chrome_options)
                self.logger.debug("使用系统ChromeDriver")
            except Exception:
                # 回退到自动下载
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.debug("使用自动下载的ChromeDriver")
            
            # 设置超时
            driver.set_page_load_timeout(15)
            driver.implicitly_wait(8)
            
            # 执行反检测脚本
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return driver
            
        except Exception as e:
            self.logger.error(f"创建ChromeDriver失败: {e}")
            return None
    
    def _is_driver_alive(self, driver) -> bool:
        """检查driver是否还活着"""
        try:
            # 尝试获取当前窗口句柄
            driver.current_window_handle
            return True
        except Exception:
            return False
    
    async def _cleanup_idle_drivers(self):
        """清理闲置的driver"""
        current_time = time.time()
        
        # 每分钟检查一次
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = current_time
        
        # 找到需要清理的driver
        to_cleanup = []
        for driver_type, last_used in self._last_used.items():
            if current_time - last_used > self._max_idle_time:
                to_cleanup.append(driver_type)
        
        # 清理闲置的driver
        for driver_type in to_cleanup:
            await self._close_driver(driver_type)
            self.logger.info(f"清理闲置WebDriver: {driver_type}")
    
    async def _close_driver(self, driver_type: str):
        """关闭指定的driver"""
        if driver_type in self._drivers:
            try:
                driver = self._drivers[driver_type]
                driver.quit()
            except Exception as e:
                self.logger.warning(f"关闭WebDriver {driver_type} 失败: {e}")
            finally:
                del self._drivers[driver_type]
                if driver_type in self._last_used:
                    del self._last_used[driver_type]
    
    async def close_all_drivers(self):
        """关闭所有driver"""
        driver_types = list(self._drivers.keys())
        for driver_type in driver_types:
            await self._close_driver(driver_type)
        self.logger.info("所有WebDriver已关闭")
    
    async def get_search_driver(self, proxy: Optional[str] = None) -> Optional[webdriver.Chrome]:
        """获取用于搜索的WebDriver"""
        driver_type = f"search_{hash(proxy) if proxy else 'direct'}"
        return await self.get_driver(driver_type, proxy=proxy)
    
    async def get_gov_driver(self, proxy: Optional[str] = None) -> Optional[webdriver.Chrome]:
        """获取用于政府网的WebDriver"""
        driver_type = f"gov_{hash(proxy) if proxy else 'direct'}"
        return await self.get_driver(driver_type, proxy=proxy)


# 全局WebDriver管理器实例
_webdriver_manager = None


async def get_webdriver_manager() -> WebDriverManager:
    """获取WebDriver管理器单例"""
    global _webdriver_manager
    if _webdriver_manager is None:
        _webdriver_manager = WebDriverManager()
    return _webdriver_manager


async def get_search_driver(proxy: Optional[str] = None) -> Optional[webdriver.Chrome]:
    """快速获取搜索WebDriver"""
    manager = await get_webdriver_manager()
    return await manager.get_search_driver(proxy)


async def get_gov_driver(proxy: Optional[str] = None) -> Optional[webdriver.Chrome]:
    """快速获取政府网WebDriver"""
    manager = await get_webdriver_manager()
    return await manager.get_gov_driver(proxy)


async def cleanup_webdrivers():
    """清理所有WebDriver"""
    global _webdriver_manager
    if _webdriver_manager:
        await _webdriver_manager.close_all_drivers() 