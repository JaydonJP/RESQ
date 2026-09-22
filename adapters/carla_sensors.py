"""Optional CARLA 0.9.x RGB/LiDAR rig for the sensor-realistic showcase."""

from __future__ import annotations

import importlib
import queue
from typing import Any

from .base import AdapterUnavailable


class CarlaSensorRig:
    def __init__(self, host: str = "127.0.0.1", port: int = 2000) -> None:
        self.host = host
        self.port = port
        self.client: Any = None
        self.world: Any = None
        self.sensors: list[Any] = []
        self.camera_queue: queue.Queue[Any] = queue.Queue(maxsize=4)
        self.lidar_queue: queue.Queue[Any] = queue.Queue(maxsize=4)

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("carla") is not None

    def connect(self) -> None:
        if not self.available:
            raise AdapterUnavailable("CARLA Python API is not installed")
        carla = importlib.import_module("carla")
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(8.0)
        self.world = self.client.get_world()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)

    def attach(self, ego_vehicle: Any) -> None:
        if self.world is None:
            raise AdapterUnavailable("CARLA sensor rig is not connected")
        carla = importlib.import_module("carla")
        blueprints = self.world.get_blueprint_library()
        camera = blueprints.find("sensor.camera.rgb")
        camera.set_attribute("image_size_x", "1280")
        camera.set_attribute("image_size_y", "720")
        camera.set_attribute("fov", "100")
        camera.set_attribute("sensor_tick", "0.05")
        lidar = blueprints.find("sensor.lidar.ray_cast")
        lidar.set_attribute("channels", "32")
        lidar.set_attribute("range", "70")
        lidar.set_attribute("rotation_frequency", "20")
        lidar.set_attribute("points_per_second", "100000")
        camera_actor = self.world.spawn_actor(
            camera,
            carla.Transform(carla.Location(x=1.5, z=1.8)),
            attach_to=ego_vehicle,
            attachment_type=carla.AttachmentType.Rigid,
        )
        lidar_actor = self.world.spawn_actor(
            lidar,
            carla.Transform(carla.Location(z=2.0)),
            attach_to=ego_vehicle,
            attachment_type=carla.AttachmentType.Rigid,
        )
        camera_actor.listen(lambda data: self._replace(self.camera_queue, data))
        lidar_actor.listen(lambda data: self._replace(self.lidar_queue, data))
        self.sensors = [camera_actor, lidar_actor]

    @staticmethod
    def _replace(target: queue.Queue[Any], value: Any) -> None:
        if target.full():
            target.get_nowait()
        target.put_nowait(value)

    def close(self) -> None:
        for sensor in self.sensors:
            sensor.stop()
            sensor.destroy()
        self.sensors.clear()
        if self.world is not None:
            settings = self.world.get_settings()
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None
            self.world.apply_settings(settings)
