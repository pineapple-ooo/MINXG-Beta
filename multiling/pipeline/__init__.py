"""
pipeline.py — 数据管道系统

提供声明式数据管道构建，支持：
  - 阶段化数据处理（Stage）
  - 数据源抽象（Source）
  - 数据目标抽象（Sink）
  - 中间件/处理器链（Middleware）
  - 错误处理与重试
  - 流式处理支持
"""

import asyncio
import json
import time
import uuid
from typing import (
    Any, AsyncGenerator, Callable, Dict, Generator, Generic,
    Iterator, List, Optional, TypeVar, Union
)
from dataclasses import dataclass, field
from enum import Enum


T = TypeVar("T")
R = TypeVar("R")


class PipelineStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DataRecord:
    """管道中的数据记录"""
    id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:10]}")
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    pipeline_id: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "data": self.data,
            "metadata": self.metadata, "timestamp": self.timestamp,
            "source": self.source, "error": self.error,
        }


class Stage:
    """管道处理阶段"""

    def __init__(
        self,
        name: str,
        processor: Union[Callable, None] = None,
        filter_fn: Union[Callable, None] = None,
        transform_fn: Union[Callable, None] = None,
        max_concurrency: int = 1,
        retry_count: int = 3,
        timeout: float = 60.0,
    ):
        self.name = name
        self.processor = processor      # 同步/异步处理函数
        self.filter_fn = filter_fn      # 过滤函数（返回 True 保留）
        self.transform_fn = transform_fn  # 转换函数
        self.max_concurrency = max_concurrency
        self.retry_count = retry_count
        self.timeout = timeout
        self._stats = {"processed": 0, "filtered": 0, "errors": 0}

    async def process(self, record: DataRecord) -> Optional[DataRecord]:
        """处理单条记录"""
        # 过滤
        if self.filter_fn:
            try:
                if asyncio.iscoroutinefunction(self.filter_fn):
                    keep = await self.filter_fn(record)
                else:
                    keep = self.filter_fn(record)
                if not keep:
                    self._stats["filtered"] += 1
                    return None
            except Exception as e:
                record.error = f"Filter error: {e}"
                self._stats["errors"] += 1
                return record

        # 转换
        if self.transform_fn:
            try:
                if asyncio.iscoroutinefunction(self.transform_fn):
                    record.data = await self.transform_fn(record.data)
                else:
                    record.data = self.transform_fn(record.data)
            except Exception as e:
                record.error = f"Transform error: {e}"
                self._stats["errors"] += 1
                return record

        # 处理器
        if self.processor:
            try:
                if asyncio.iscoroutinefunction(self.processor):
                    result = await self.processor(record)
                else:
                    result = self.processor(record)
                if result is not None:
                    if isinstance(result, DataRecord):
                        record = result
                    else:
                        record.data = result
            except Exception as e:
                record.error = f"Processor error: {e}"
                self._stats["errors"] += 1
                return record

        self._stats["processed"] += 1
        return record

    def get_stats(self) -> Dict:
        return self._stats.copy()


class DataSource:
    """数据源抽象"""

    def __init__(self, name: str):
        self.name = name

    def __aiter__(self):
        return self

    async def __anext__(self) -> DataRecord:
        raise NotImplementedError

    def iter(self) -> Iterator[DataRecord]:
        """同步迭代器"""
        return self._sync_iter()

    def _sync_iter(self) -> Iterator[DataRecord]:
        raise NotImplementedError


class ListSource(DataSource):
    """列表数据源"""

    def __init__(self, name: str, data: List[Any]):
        super().__init__(name)
        self._data = data

    async def __anext__(self) -> DataRecord:
        if not hasattr(self, "_index"):
            self._index = 0
        if self._index >= len(self._data):
            raise StopAsyncIteration
        item = self._data[self._index]
        self._index += 1
        return DataRecord(data=item, source=self.name)

    def _sync_iter(self) -> Iterator[DataRecord]:
        for item in self._data:
            yield DataRecord(data=item, source=self.name)


class GeneratorSource(DataSource):
    """生成器数据源"""

    def __init__(self, name: str, generator: Callable):
        super().__init__(name)
        self._generator = generator

    async def __anext__(self) -> DataRecord:
        if not hasattr(self, "_agen"):
            self._agen = self._generator()
        try:
            item = await self._agen.__anext__() if hasattr(self._agen, '__anext__') else next(self._agen)
            return DataRecord(data=item, source=self.name)
        except StopAsyncIteration:
            raise
        except StopIteration:
            raise StopAsyncIteration

    def _sync_iter(self) -> Iterator[DataRecord]:
        gen = self._generator()
        for item in gen:
            yield DataRecord(data=item, source=self.name)


class DataSink:
    """数据目标抽象"""

    def __init__(self, name: str):
        self.name = name
        self._collected: List[DataRecord] = []

    async def consume(self, record: DataRecord):
        self._collected.append(record)

    def consume_sync(self, record: DataRecord):
        self._collected.append(record)

    def get_results(self) -> List[Any]:
        return [r.data for r in self._collected]

    def get_records(self) -> List[DataRecord]:
        return self._collected.copy()

    def clear(self):
        self._collected.clear()

    def export_json(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self._collected], f,
                      ensure_ascii=False, indent=2, default=str)


class Pipeline:
    """
    数据管道

    用法:
        pipeline = Pipeline("my_pipeline")
        pipeline.source(ListSource("input", [1, 2, 3, 4, 5]))
        pipeline.add_stage(Stage("double", transform_fn=lambda x: x * 2))
        pipeline.add_stage(Stage("filter_even", filter_fn=lambda r: r.data % 2 == 0))
        pipeline.sink(DataSink("output"))
        result = pipeline.run()
    """

    def __init__(self, name: str = "pipeline"):
        self.name = name
        self.id = f"pipe_{uuid.uuid4().hex[:12]}"
        self._source: Optional[DataSource] = None
        self._stages: List[Stage] = []
        self._sink: Optional[DataSink] = None
        self._status = PipelineStatus.IDLE
        self._stats = {
            "total_input": 0, "total_output": 0,
            "total_errors": 0, "stages_processed": 0,
        }

    def source(self, source: DataSource) -> "Pipeline":
        """设置数据源"""
        self._source = source
        return self

    def add_stage(self, stage: Stage) -> "Pipeline":
        """添加处理阶段"""
        self._stages.append(stage)
        return self

    def sink(self, sink: DataSink) -> "Pipeline":
        """设置数据目标"""
        self._sink = sink
        return self

    async def run_async(self) -> Dict:
        """异步执行管道"""
        if not self._source:
            return {"error": "No source configured"}
        if not self._sink:
            self._sink = DataSink("default_sink")

        self._status = PipelineStatus.RUNNING
        self._stats["total_input"] = 0
        self._stats["total_output"] = 0
        self._stats["total_errors"] = 0

        try:
            async for record in self._source:
                self._stats["total_input"] += 1
                current = record

                for stage in self._stages:
                    if current is None:
                        break
                    current = await stage.process(current)
                    if current and current.error:
                        self._stats["total_errors"] += 1

                if current and not current.error:
                    await self._sink.consume(current)
                    self._stats["total_output"] += 1

            self._status = PipelineStatus.COMPLETED
            self._stats["stages_processed"] = len(self._stages)

        except Exception as e:
            self._status = PipelineStatus.FAILED
            return {
                "error": str(e),
                "status": "failed",
                "stats": self._stats,
            }

        return {
            "status": "completed",
            "stats": self._stats,
            "output_count": self._stats["total_output"],
        }

    def run(self) -> Dict:
        """同步执行管道"""
        import asyncio
        return asyncio.run(self.run_async())

    def run_sync(self) -> Dict:
        """同步执行管道（使用同步迭代器）"""
        if not self._source:
            return {"error": "No source configured"}
        if not self._sink:
            self._sink = DataSink("default_sink")

        self._status = PipelineStatus.RUNNING
        self._stats = {"total_input": 0, "total_output": 0,
                       "total_errors": 0, "stages_processed": 0}

        try:
            for record in self._source.iter():
                self._stats["total_input"] += 1
                current = record

                for stage in self._stages:
                    if current is None:
                        break
                    # 同步执行
                    try:
                        if stage.filter_fn:
                            keep = stage.filter_fn(current)
                            if not keep:
                                stage._stats["filtered"] += 1
                                current = None
                                continue
                        if stage.transform_fn and current:
                            current.data = stage.transform_fn(current.data)
                        if stage.processor and current:
                            result = stage.processor(current)
                            if result is not None:
                                if isinstance(result, DataRecord):
                                    current = result
                                else:
                                    current.data = result
                    except Exception as e:
                        if current:
                            current.error = str(e)
                        stage._stats["errors"] += 1
                        self._stats["total_errors"] += 1
                        current = None

                if current and not current.error:
                    self._sink.consume_sync(current)
                    self._stats["total_output"] += 1

            self._status = PipelineStatus.COMPLETED
            self._stats["stages_processed"] = len(self._stages)

        except Exception as e:
            self._status = PipelineStatus.FAILED
            return {"error": str(e), "status": "failed", "stats": self._stats}

        return {"status": "completed", "stats": self._stats,
                "output_count": self._stats["total_output"]}

    def get_stats(self) -> Dict:
        stage_stats = [s.get_stats() for s in self._stages]
        return {
            "pipeline": self.name,
            "id": self.id,
            "status": self._status.value,
            **self._stats,
            "stage_stats": stage_stats,
        }


class PipelineRegistry:
    """管道注册表"""

    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}

    def register(self, pipeline: Pipeline):
        self._pipelines[pipeline.id] = pipeline

    def get(self, pipeline_id: str) -> Optional[Pipeline]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> List[Dict]:
        return [{"id": p.id, "name": p.name,
                 "status": p._status.value,
                 "stages": len(p._stages)}
                for p in self._pipelines.values()]

    def run_pipeline(self, pipeline_id: str) -> Dict:
        if pipeline_id not in self._pipelines:
            return {"error": f"Pipeline not found: {pipeline_id}"}
        return self._pipelines[pipeline_id].run()