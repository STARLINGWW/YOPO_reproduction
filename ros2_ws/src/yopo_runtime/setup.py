from setuptools import find_packages, setup

setup(name="yopo_runtime", version="0.1.0", packages=find_packages(),
      data_files=[("share/ament_index/resource_index/packages", ["resource/yopo_runtime"]),
                  ("share/yopo_runtime", ["package.xml"])],
      install_requires=["setuptools"], zip_safe=True,
      maintainer="YOPO reproduction", maintainer_email="maintainer@example.invalid",
      description="ROS2 runtime and timing guards for YOPO experiments", license="MIT",
      tests_require=["pytest"])
