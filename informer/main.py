"""
Chiphell二手区监控工具入口文件，集成了Web配置界面
"""

import os
import time
import threading
import urllib3
import warnings
import yaml
import schedule
from loguru import logger
import sys
from functools import wraps
import requests  # 用于验证 Turnstile 令牌

# 尝试导入Flask相关模块
try:
    from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    # 在主函数中会再次警告

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# 全局变量
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'config.yaml')
notifier_instance = None
config_lock = threading.Lock()
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 30 * 60  # 30分钟

# 全局变量，存储Flask应用实例
app = None
if FLASK_AVAILABLE:
    # 动态导入，因为这些模块依赖于可能未安装的库
    from informer.config import load_config
    from informer.logger import setup_logger
    from informer.database import Database
    from informer.notifier import MultiRobotNotifier, DingTalkNotifier
    from informer.expiration_manager import ExpirationManager
    from informer.proxy_manager import ProxyManager
    from informer.monitor import ChiphellMonitor
    from datetime import datetime

    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'static'))
    app.secret_key = os.urandom(24)
    
    # 添加自定义模板过滤器
    @app.template_filter('strptime')
    def _jinja2_filter_strptime(date_string, format_string):
        """将日期字符串转换为日期对象"""
        try:
            return datetime.strptime(date_string, format_string)
        except:
            # 如果转换失败，返回当前时间
            return datetime.now()

def load_web_config():
    """加载配置文件 (为Web界面提供)"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            return {"error": "配置文件不存在"}
    except Exception as e:
        return {"error": str(e)}

def save_config(config):
    """保存配置到文件"""
    try:
        with config_lock:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            if notifier_instance and "dingtalk" in config and "robots" in config["dingtalk"]:
                from informer.config import DingTalkRobot, UserConfig
                
                robot_objects = []
                for robot_dict in config["dingtalk"]["robots"]:
                    users = []
                    if "users" in robot_dict:
                        for phone, user_data in robot_dict["users"].items():
                            users.append(UserConfig(
                                phone=str(phone),
                                keywords=user_data.get("keywords", []),
                                always_at=user_data.get("always_at", False),
                                expire_date=user_data.get("expire_date", ""),
                                is_permanent=user_data.get("is_permanent", True)
                            ))
                    
                    robot_objects.append(DingTalkRobot(
                        name=robot_dict.get("name", "未命名机器人"),
                        token=robot_dict.get("token", ""),
                        secret=robot_dict.get("secret", ""),
                        enabled=robot_dict.get("enabled", True),
                        receive_all=robot_dict.get("receive_all", True),
                        users=users
                    ))
                
                notifier_instance.update_robots(robot_objects)
                logger.info(f"已实时更新钉钉机器人配置，共 {len(robot_objects)} 个机器人")
        
        return True
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return str(e)

def get_password():
    """从配置文件中获取密码"""
    config = load_web_config()
    return config.get("web_password", "")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        password = get_password()
        if password and not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_turnstile(token, secret_key, remoteip=None):
    """
    验证 Cloudflare Turnstile 令牌
    
    Args:
        token: 从前端获取的 Turnstile 令牌
        secret_key: Turnstile 密钥
        remoteip: 用户的 IP 地址（可选）
        
    Returns:
        bool: 验证是否成功
    """
    if not token or not secret_key:
        return False
    
    data = {
        "secret": secret_key,
        "response": token
    }
    
    if remoteip:
        data["remoteip"] = remoteip
    
    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            timeout=10
        )
        result = response.json()
        return result.get("success", False)
    except Exception as e:
        logger.error(f"验证 Turnstile 令牌时出错: {e}")
        return False

def get_turnstile_config():
    """获取 Turnstile 配置"""
    config = load_web_config()
    turnstile_config = config.get("turnstile", {})
    return {
        "site_key": turnstile_config.get("site_key", ""),
        "secret_key": turnstile_config.get("secret_key", ""),
        "enabled": turnstile_config.get("enabled", False)
    }

def get_client_ip():
    """
    获取客户端真实 IP 地址，支持反向代理
    
    Returns:
        str: 客户端 IP 地址
    """
    if request.headers.get('X-Forwarded-For'):
        # 如果有 X-Forwarded-For 头，取第一个 IP（最接近用户的 IP）
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        # 某些代理使用 X-Real-IP
        ip = request.headers.get('X-Real-IP')
    else:
        # 直接连接的情况
        ip = request.remote_addr
    
    return ip

if FLASK_AVAILABLE:
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        ip_address = get_client_ip()
        now = time.time()

        if ip_address in login_attempts:
            attempt_info = login_attempts[ip_address]
            lockout_time = attempt_info.get('lockout_time')
            if lockout_time and now < lockout_time + LOCKOUT_DURATION:
                remaining_time = int((lockout_time + LOCKOUT_DURATION - now) / 60)
                error = f"登录失败次数过多，请在 {remaining_time} 分钟后重试。"
                return render_template('login.html', error=error)
            elif lockout_time and now >= lockout_time + LOCKOUT_DURATION:
                del login_attempts[ip_address]

        password = get_password()
        if not password:
            session['logged_in'] = True
            return redirect(url_for('index'))

        # 获取 Turnstile 配置
        turnstile_config = get_turnstile_config()
        site_key = turnstile_config["site_key"]
        
        error = None
        if request.method == 'POST':
            # 验证 Turnstile 令牌
            turnstile_token = request.form.get('cf-turnstile-response')
            turnstile_passed = True  # 默认通过
            
            if turnstile_config["enabled"]:
                turnstile_passed = verify_turnstile(
                    turnstile_token, 
                    turnstile_config["secret_key"],
                    ip_address
                )
                if not turnstile_passed:
                    error = "人机验证失败，请重试。"
                    return render_template('login.html', error=error, site_key=site_key)
            
            if request.form['password'] == password and turnstile_passed:
                if ip_address in login_attempts:
                    del login_attempts[ip_address]
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                if ip_address not in login_attempts:
                    login_attempts[ip_address] = {'failures': 0}
                
                login_attempts[ip_address]['failures'] += 1
                
                if login_attempts[ip_address]['failures'] >= MAX_LOGIN_ATTEMPTS:
                    login_attempts[ip_address]['lockout_time'] = now
                    error = "登录失败次数过多，您的IP已被锁定30分钟。"
                else:
                    remaining_attempts = MAX_LOGIN_ATTEMPTS - login_attempts[ip_address]['failures']
                    error = f"密码错误，您还有 {remaining_attempts} 次尝试机会。"
        
        return render_template('login.html', error=error, site_key=site_key)

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def index():
        from datetime import datetime
        
        config = load_web_config()
        if "error" in config:
            flash(f"加载配置失败: {config['error']}", "danger")
            config = {}
        return render_template('index.html', config=config, now=datetime.now())

    @app.route('/add_robot', methods=['POST'])
    @login_required
    def add_robot():
        try:
            config = load_web_config()
            if "dingtalk" not in config:
                config["dingtalk"] = {}
            if "robots" not in config["dingtalk"]:
                config["dingtalk"]["robots"] = []
            
            new_robot = {
                "name": request.json.get("name", "新机器人"),
                "token": request.json.get("token", ""),
                "secret": request.json.get("secret", ""),
                "receive_all": request.json.get("receive_all", True),
                "enabled": True,
                "users": {}
            }
            
            config["dingtalk"]["robots"].append(new_robot)
            result = save_config(config)
            
            if result is True:
                return jsonify({"status": "success", "message": "机器人添加成功"})
            else:
                return jsonify({"status": "error", "message": f"添加失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"添加失败: {str(e)}"})

    @app.route('/add_user', methods=['POST'])
    @login_required
    def add_user():
        try:
            robot_index = int(request.json.get("robot_index", 0))
            phone = request.json.get("phone", "")
            always_at = request.json.get("always_at", False)
            
            config = load_web_config()
            
            if not phone or not phone.isdigit() or len(phone) != 11:
                return jsonify({"status": "error", "message": "手机号格式不正确"})
            
            if "dingtalk" not in config or "robots" not in config["dingtalk"] or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "机器人配置不存在"})
            
            robot = config["dingtalk"]["robots"][robot_index]
            if "users" not in robot:
                robot["users"] = {}
            
            robot["users"][phone] = {
                "always_at": always_at,
                "keywords": [],
                "expire_date": request.json.get("expire_date", ""),
                "is_permanent": request.json.get("is_permanent", True)
            }
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "用户添加成功"})
            else:
                return jsonify({"status": "error", "message": f"添加失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"添加失败: {str(e)}"})

    @app.route('/add_keyword', methods=['POST'])
    @login_required
    def add_keyword():
        try:
            robot_index = int(request.json.get("robot_index", 0))
            phone = request.json.get("phone", "")
            keyword = request.json.get("keyword", "").strip()
            
            if not keyword:
                return jsonify({"status": "error", "message": "关键词不能为空"})
            
            config = load_web_config()
            
            if "dingtalk" not in config or "robots" not in config["dingtalk"] or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "机器人配置不存在"})
            
            robot = config["dingtalk"]["robots"][robot_index]
            if "users" not in robot or str(phone) not in robot["users"]:
                return jsonify({"status": "error", "message": "用户不存在"})
            
            if "keywords" not in robot["users"][str(phone)]:
                robot["users"][str(phone)]["keywords"] = []
            
            robot["users"][str(phone)]["keywords"].append(keyword)
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "关键词添加成功"})
            else:
                return jsonify({"status": "error", "message": f"添加失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"添加失败: {str(e)}"})

    @app.route('/delete_keyword', methods=['POST'])
    @login_required
    def delete_keyword():
        try:
            robot_index = int(request.json.get("robot_index", 0))
            phone = str(request.json.get("phone", ""))
            keyword = request.json.get("keyword", "").strip()

            if not keyword:
                return jsonify({"status": "error", "message": "关键词不能为空"})

            config = load_web_config()

            if "dingtalk" not in config or "robots" not in config["dingtalk"] or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "机器人配置不存在"})

            robot = config["dingtalk"]["robots"][robot_index]
            if "users" not in robot or phone not in robot["users"]:
                return jsonify({"status": "error", "message": "用户不存在"})

            if "keywords" in robot["users"][phone] and keyword in robot["users"][phone]["keywords"]:
                robot["users"][phone]["keywords"].remove(keyword)
            else:
                return jsonify({"status": "error", "message": "要删除的关键词不存在"})

            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "关键词删除成功"})
            else:
                return jsonify({"status": "error", "message": f"删除失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"删除失败: {str(e)}"})

    @app.route('/update_robot', methods=['POST'])
    @login_required
    def update_robot():
        try:
            robot_index = int(request.json.get("robot_index", -1))
            config = load_web_config()
            
            if robot_index < 0 or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "无效的机器人索引"})
            
            # 正确处理前端发送的嵌套数据结构
            robot_data = request.json.get("robot_data", {})
            if robot_data:
                config["dingtalk"]["robots"][robot_index]["name"] = robot_data.get("name", "未命名机器人")
                config["dingtalk"]["robots"][robot_index]["token"] = robot_data.get("token", "")
                config["dingtalk"]["robots"][robot_index]["secret"] = robot_data.get("secret", "")
                config["dingtalk"]["robots"][robot_index]["receive_all"] = robot_data.get("receive_all", True)
                config["dingtalk"]["robots"][robot_index]["enabled"] = robot_data.get("enabled", True)
            else:
                # 兼容不使用嵌套结构的请求
                config["dingtalk"]["robots"][robot_index]["name"] = request.json.get("name", "未命名机器人")
                config["dingtalk"]["robots"][robot_index]["token"] = request.json.get("token", "")
                config["dingtalk"]["robots"][robot_index]["secret"] = request.json.get("secret", "")
                config["dingtalk"]["robots"][robot_index]["receive_all"] = request.json.get("receive_all", True)
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "机器人配置更新成功"})
            else:
                return jsonify({"status": "error", "message": f"更新失败: {result}"})
        except Exception as e:
            import traceback
            trace = traceback.format_exc()
            return jsonify({"status": "error", "message": f"更新失败: {str(e)}", "traceback": trace})

    @app.route('/delete_user', methods=['POST'])
    @login_required
    def delete_user():
        try:
            robot_index = int(request.json.get("robot_index", -1))
            phone = str(request.json.get("phone", ""))
            config = load_web_config()

            if robot_index < 0 or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "无效的机器人索引"})

            if "users" in config["dingtalk"]["robots"][robot_index] and phone in config["dingtalk"]["robots"][robot_index]["users"]:
                del config["dingtalk"]["robots"][robot_index]["users"][phone]
                result = save_config(config)
                if result is True:
                    return jsonify({"status": "success", "message": "用户删除成功"})
                else:
                    return jsonify({"status": "error", "message": f"删除失败: {result}"})
            else:
                return jsonify({"status": "error", "message": "用户不存在"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"删除失败: {str(e)}"})

    @app.route('/save_llm_config', methods=['POST'])
    @login_required
    def save_llm_config():
        try:
            request_data = request.json
            config = load_web_config()
            if "error" in config:
                return jsonify({"status": "error", "message": f"加载配置失败: {config['error']}"})
            
            config["llm_config"] = request_data
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "LLM配置保存成功"})
            else:
                return jsonify({"status": "error", "message": f"保存失败: {result}"})
        except Exception as e:
            import traceback
            trace = traceback.format_exc()
            return jsonify({"status": "error", "message": f"保存失败: {str(e)}", "traceback": trace})

    @app.route('/delete_robot', methods=['POST'])
    @login_required
    def delete_robot():
        try:
            robot_index = int(request.json.get("robot_index", -1))
            config = load_web_config()
            
            if robot_index < 0 or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": f"无效的机器人索引: {robot_index}"})
            
            del config["dingtalk"]["robots"][robot_index]
            result = save_config(config)
            
            if result is True:
                return jsonify({"status": "success", "message": "机器人删除成功"})
            else:
                return jsonify({"status": "error", "message": f"删除失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"删除失败: {str(e)}"})

    @app.route('/toggle_always_at', methods=['POST'])
    @login_required
    def toggle_always_at():
        try:
            robot_index = int(request.json.get("robot_index"))
            phone = str(request.json.get("phone"))
            config = load_web_config()

            if robot_index < 0 or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "无效的机器人索引"})
            
            user_data = config["dingtalk"]["robots"][robot_index]["users"].get(phone)
            if not user_data:
                return jsonify({"status": "error", "message": "用户不存在"})

            user_data["always_at"] = not user_data.get("always_at", False)
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "切换成功"})
            else:
                return jsonify({"status": "error", "message": f"切换失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"切换失败: {str(e)}"})
            
    @app.route('/update_user_expiration', methods=['POST'])
    @login_required
    def update_user_expiration():
        try:
            robot_index = int(request.json.get("robot_index"))
            phone = str(request.json.get("phone"))
            expire_date = request.json.get("expire_date", "")
            is_permanent = bool(request.json.get("is_permanent", True))
            config = load_web_config()

            if robot_index < 0 or robot_index >= len(config["dingtalk"]["robots"]):
                return jsonify({"status": "error", "message": "无效的机器人索引"})
            
            user_data = config["dingtalk"]["robots"][robot_index]["users"].get(phone)
            if not user_data:
                return jsonify({"status": "error", "message": "用户不存在"})

            # 更新有效期信息
            user_data["expire_date"] = expire_date
            user_data["is_permanent"] = is_permanent
            
            result = save_config(config)
            if result is True:
                return jsonify({"status": "success", "message": "有效期更新成功"})
            else:
                return jsonify({"status": "error", "message": f"更新失败: {result}"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"更新失败: {str(e)}"})

def run_web_app():
    """运行Web配置界面"""
    if FLASK_AVAILABLE:
        host = "0.0.0.0"  # 默认绑定到所有接口
        port = 5000
        debug = False
        
        # 检查是否在 Docker 环境中运行
        in_docker = os.environ.get('DOCKER_ENV', '').lower() == 'true'
        if in_docker:
            logger.info("检测到 Docker 环境，使用 Docker 特定设置")
        
        logger.info(f"正在启动Web配置界面，请访问 http://{host}:{port}")
        app.run(host=host, port=port, debug=debug)
    else:
        pass

def check_expiring_users():
    """定时检查并通知即将过期的用户"""
    try:
        global notifier_instance
        
        if not notifier_instance:
            logger.warning("无法执行过期检查：通知器实例不可用")
            return
            
        logger.info("开始执行用户过期检查...")
        
        # 导入过期管理器
        from informer.expiration_manager import ExpirationManager
        expiration_manager = ExpirationManager(notifier_instance)
        expiration_manager.check_and_notify_expiring_users()
        
        logger.info("用户过期检查完成")
    except Exception as e:
        logger.error(f"执行过期检查时出错：{e}")

def main():
    """主函数"""
    global notifier_instance

    if not FLASK_AVAILABLE:
        logger.error("未安装Flask或其依赖，无法启动。请运行 'pip install Flask'。")
        return

    from informer.config import load_config
    from informer.logger import setup_logger

    config = load_config()
    setup_logger(
        config.log_config.file,
        config.log_config.max_size,
        config.log_config.max_backups,
        config.log_config.max_age,
        config.log_config.compress,
        config.log_config.level
    )
    
    # 设置每天上午12点检查用户过期情况（改为12点）
    schedule.every().day.at("12:00").do(check_expiring_users)
    
    # 启动定时任务线程
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
            
    schedule_thread = threading.Thread(target=run_schedule, daemon=True)
    schedule_thread.start()
    logger.info("已启动用户过期检查定时任务")

    if len(sys.argv) > 1 and sys.argv[1] == '--web':
        logger.info("以--web模式启动，只运行Web配置界面。")
        run_web_app()
        return

    # 先启动监控线程，初始化notifier_instance
    monitor_thread = threading.Thread(target=start_monitor, args=(config,), daemon=True)
    monitor_thread.start()
    
    # 等待notifier_instance初始化完成
    wait_count = 0
    while notifier_instance is None and wait_count < 10:
        time.sleep(0.5)
        wait_count += 1
    
    # 在notifier_instance初始化完成后，执行一次用户过期检查
    if notifier_instance:
        threading.Thread(target=check_expiring_users, daemon=True).start()
        logger.info("已触发首次用户过期检查")
    else:
        logger.warning("等待通知器初始化超时，首次过期检查将在下次定时任务触发时执行")
    
    run_web_app()

def start_monitor(config):
    """启动监控逻辑"""
    global notifier_instance
    try:
        from informer.database import Database
        from informer.notifier import MultiRobotNotifier
        from informer.proxy_manager import ProxyManager
        from informer.monitor import ChiphellMonitor

        database = Database()
        
        proxy_manager = None
        if config.proxy_pool_api:
            proxy_manager = ProxyManager(config.proxy_pool_api)
        
        notifier_instance = MultiRobotNotifier(config.dingtalk.robots)
        
        if config.llm_config:
            logger.info(f"LLM配置已加载，使用模型: {config.llm_config.model}")
        else:
            logger.info("未配置LLM，内容分析功能将被禁用")
        
        monitor = ChiphellMonitor(
            config.cookies,
            None,
            notifier_instance,
            database,
            config.wait_time_range,
            proxy_manager,
            config.llm_config
        )
        logger.info("监控器初始化完成，开始在后台监控...")
        
        monitor.monitor()
    
    except KeyboardInterrupt:
        logger.info("监控线程被中断")
    except Exception as e:
        logger.error(f"监控线程运行出错: {e}")
        
        try:
            if notifier_instance:
                notifier_instance.report_error("程序异常", str(e))
        except:
            pass
        
        time.sleep(5)
    finally:
        try:
            if 'database' in locals() and hasattr(database, 'close'):
                database.close()
        except:
            pass
        
        logger.info("监控线程已退出")

if __name__ == "__main__":
    main() 