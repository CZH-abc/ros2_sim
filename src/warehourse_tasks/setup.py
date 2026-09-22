import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'warehourse_tasks'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # ament_python 不会自动拷目录，必须手动把 launch/ 和 config/ 装进 share/。
        # 少了这一段：ros2 launch 报 "no launch file named tasks.launch.py"，
        # 而 colcon build 照样是 SUCCESSFUL —— 最容易被误判的一种失败。
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=False,
    maintainer='robot',
    maintainer_email='robot@todo.todo',
    description='仓库任务调度：按路线依次调用 Nav2 的 navigate_to_pose',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        # 左边是 ros2 run 后面的命令名，右边是 模块文件.函数:入口函数
        'console_scripts': [
            'task_sequencer = warehourse_tasks.task_sequencer:main',
        ],
    },
)
