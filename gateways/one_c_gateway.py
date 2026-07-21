"""
OneCGateway — интерфейс к 1С:ERP.

ADR-0011 Принцип П7: OneCGateway интерфейс с двумя реализациями.
Бизнес-логика НЕ знает, файл под ней или HTTP.

Реализации:
- FileGateway — XML-обмен (для препилота, Техинком)
- HttpGateway — HTTP-сервис 1С (заглушка, для продуктивизации)

Контракт (НЕ меняется между реализациями):
- get_nomenclature(filter) -> List[Item]      # НСИ из 1С
- get_materials() -> List[Material]            # материалы
- get_equipment() -> List[Equipment]           # оборудование
- get_professions_tariffs() -> List[Profession]  # профессии + тарифы
- get_resource_spec(ref_1c) -> ResourceSpec   # готовая РС
- create_resource_spec(rs) -> str (ref_1c)     # записать
- update_resource_spec(ref_1c, rs) -> bool
- sync_log(operation) -> None
"""
from __future__ import annotations

import json
import logging
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# DTO
# ============================================================

@dataclass
class OneCItem:
    ref_1c: str
    designation: str
    name: str
    level: str
    mass_kg: Optional[float] = None
    material_ref: Optional[str] = None
    parent_ref: Optional[str] = None
    sourcing: str = "make"


@dataclass
class OneCMaterial:
    ref_1c: str
    code: str
    name: str
    unit: str
    price_per_unit: float


@dataclass
class OneCEquipment:
    ref_1c: str
    inventory_no: str
    name: str
    workshop_ref: str


@dataclass
class OneCProfession:
    ref_1c: str
    code: str
    name: str
    grade: int
    hourly_rate: float


@dataclass
class OneCResourceSpec:
    """Ресурсная спецификация (выход rs_factory)."""
    ref_1c: Optional[str]
    item_ref: str
    tech_card_ref: Optional[str]
    version: int
    profile_code: str
    rows: List[Dict[str, Any]] = field(default_factory=list)
    # rows[i] = {
    #   "stage": "01/01", "op_number": 5, "name": "Резка",
    #   "profession": "Р-3", "qty": 1, "time_setup_min": 6, "time_per_unit_min": 12,
    #   "material_code": "09Г2С", "material_qty": 8.5, "material_unit": "кг",
    #   "equipment": "НГ-6,3"
    # }
    change_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_xml(self) -> str:
        """Сериализовать в XML для обмена с 1С:ERP."""
        from xml.sax.saxutils import escape
        rows_xml = []
        for r in self.rows:
            row_parts = []
            for k, v in r.items():
                if v is None:
                    continue
                row_parts.append(f"      <{k}>{escape(str(v))}</{k}>")
            rows_xml.append("    <row>\n" + "\n".join(row_parts) + "\n    </row>")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ResourceSpec xmlns="http://v8.1c.ru/resource-spec">\n'
            f'  <item_ref>{escape(str(self.item_ref))}</item_ref>\n'
            f'  <tech_card_ref>{escape(str(self.tech_card_ref or ""))}</tech_card_ref>\n'
            f'  <version>{self.version}</version>\n'
            f'  <profile_code>{escape(str(self.profile_code))}</profile_code>\n'
            f'  <change_reason>{escape(str(self.change_reason or ""))}</change_reason>\n'
            f'  <rows count="{len(self.rows)}">\n'
            + "\n".join(rows_xml) + "\n"
            '  </rows>\n'
            '</ResourceSpec>\n'
        )


# ============================================================
# ИНТЕРФЕЙС
# ============================================================

class OneCGateway(ABC):
    """Базовый интерфейс для всех реализаций шлюза к 1С."""

    name: str = "base"
    is_connected: bool = False

    @abstractmethod
    def connect(self) -> bool:
        """Подключиться к 1С. Возвращает True при успехе."""

    @abstractmethod
    def get_nomenclature(
        self,
        level: Optional[str] = None,
        parent_ref: Optional[str] = None,
        modified_after: Optional[str] = None,
    ) -> List[OneCItem]:
        """Получить номенклатуру из 1С."""

    @abstractmethod
    def get_materials(self) -> List[OneCMaterial]:
        """Получить справочник материалов."""

    @abstractmethod
    def get_equipment(self) -> List[OneCEquipment]:
        """Получить справочник оборудования."""

    @abstractmethod
    def get_professions_tariffs(self) -> List[OneCProfession]:
        """Получить профессии + тарифные ставки."""

    @abstractmethod
    def get_resource_spec(self, ref_1c: str) -> Optional[OneCResourceSpec]:
        """Получить существующую РС из 1С по ref_1c."""

    @abstractmethod
    def create_resource_spec(self, rs: OneCResourceSpec) -> str:
        """Создать РС в 1С. Возвращает ref_1c."""

    @abstractmethod
    def update_resource_spec(self, ref_1c: str, rs: OneCResourceSpec) -> bool:
        """Обновить РС в 1С."""

    @abstractmethod
    def export_to_file(self, rs: OneCResourceSpec, path: Path) -> Path:
        """Экспорт РС в файл (XML)."""

    def sync_log(self, operation: str, details: Dict[str, Any]) -> None:
        """Лог операции. По умолчанию — в логгер."""
        logger.info(f"[{self.name}] {operation}: {json.dumps(details, ensure_ascii=False)[:200]}")


# ============================================================
# FILE GATEWAY (для препилота)
# ============================================================

class FileGateway(OneCGateway):
    """Читает/пишет XML в локальной папке `one_c_exchange/`.

    Структура:
    one_c_exchange/
        in/
            nomenclature.xml    # НСИ из 1С
            materials.xml       # материалы
            equipment.xml       # оборудование
            professions.xml     # профессии + тарифы
        out/
            rs_<item_designation>_<version>.xml  # выходные РС
    """

    name = "file"

    def __init__(self, exchange_dir: Path = None):
        self.exchange_dir = exchange_dir or Path(__file__).parent.parent / "data" / "one_c_exchange"
        self.exchange_dir.mkdir(parents=True, exist_ok=True)
        (self.exchange_dir / "in").mkdir(exist_ok=True)
        (self.exchange_dir / "out").mkdir(exist_ok=True)

    def connect(self) -> bool:
        """Проверить, что есть входные файлы (или создать пустые)."""
        self.is_connected = True
        # Создаём заглушки, если их нет
        for fname, root_tag in [
            ("nomenclature.xml", "Nomenclature"),
            ("materials.xml", "Materials"),
            ("equipment.xml", "Equipment"),
            ("professions.xml", "Professions"),
        ]:
            f = self.exchange_dir / "in" / fname
            if not f.exists():
                f.write_text(f"<?xml version='1.0' encoding='UTF-8'?>\n<{root_tag}>\n</{root_tag}>\n", encoding="utf-8")
        return True

    def get_nomenclature(
        self,
        level: Optional[str] = None,
        parent_ref: Optional[str] = None,
        modified_after: Optional[str] = None,
    ) -> List[OneCItem]:
        f = self.exchange_dir / "in" / "nomenclature.xml"
        if not f.exists():
            return []
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            logger.error(f"Invalid XML in {f}")
            return []
        items = []
        for item_el in tree.findall(".//Item"):
            ref = item_el.get("ref") or ""
            des = item_el.findtext("Designation", "")
            name = item_el.findtext("Name", "")
            lvl = item_el.get("level", "detail")
            if level and lvl != level:
                continue
            if parent_ref and item_el.get("parent_ref") != parent_ref:
                continue
            items.append(OneCItem(
                ref_1c=ref,
                designation=des,
                name=name,
                level=lvl,
                mass_kg=_try_float(item_el.findtext("Mass")),
                material_ref=item_el.get("material_ref"),
                parent_ref=item_el.get("parent_ref"),
                sourcing=item_el.get("sourcing", "make"),
            ))
        return items

    def get_materials(self) -> List[OneCMaterial]:
        f = self.exchange_dir / "in" / "materials.xml"
        if not f.exists():
            return []
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            return []
        out = []
        for m in tree.findall(".//Material"):
            out.append(OneCMaterial(
                ref_1c=m.get("ref", ""),
                code=m.findtext("Code", ""),
                name=m.findtext("Name", ""),
                unit=m.get("unit", "кг"),
                price_per_unit=_try_float(m.findtext("Price")) or 0.0,
            ))
        return out

    def get_equipment(self) -> List[OneCEquipment]:
        f = self.exchange_dir / "in" / "equipment.xml"
        if not f.exists():
            return []
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            return []
        out = []
        for e in tree.findall(".//Equipment"):
            out.append(OneCEquipment(
                ref_1c=e.get("ref", ""),
                inventory_no=e.get("inventory_no", ""),
                name=e.findtext("Name", ""),
                workshop_ref=e.get("workshop_ref", ""),
            ))
        return out

    def get_professions_tariffs(self) -> List[OneCProfession]:
        f = self.exchange_dir / "in" / "professions.xml"
        if not f.exists():
            return []
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            return []
        out = []
        for p in tree.findall(".//Profession"):
            out.append(OneCProfession(
                ref_1c=p.get("ref", ""),
                code=p.findtext("Code", ""),
                name=p.findtext("Name", ""),
                grade=int(p.get("grade", "0")),
                hourly_rate=_try_float(p.findtext("HourlyRate")) or 0.0,
            ))
        return out

    def get_resource_spec(self, ref_1c: str) -> Optional[OneCResourceSpec]:
        # В файловом режиме мы не получаем РС из 1С (только отдаём)
        return None

    def create_resource_spec(self, rs: OneCResourceSpec) -> str:
        """Создать РС в 1С — это экспорт XML в out/."""
        path = self.export_to_file(rs, self.exchange_dir / "out")
        # В реальной 1С вернётся ref_1c. У нас — путь к файлу как идентификатор
        rs.ref_1c = f"file://{path.name}"
        return rs.ref_1c

    def update_resource_spec(self, ref_1c: str, rs: OneCResourceSpec) -> bool:
        path = self.export_to_file(rs, self.exchange_dir / "out")
        return path.exists()

    def export_to_file(self, rs: OneCResourceSpec, path: Path) -> Path:
        """Экспорт РС в XML 1С."""
        # Если path — директория, сгенерируем имя
        if path.is_dir():
            designation_safe = rs.item_ref.replace("/", "_").replace(".", "_")
            path = path / ("rs_" + designation_safe + "_v" + str(rs.version) + ".xml")
        root = ET.Element("ResourceSpec", {
            "version": str(rs.version),
            "itemRef": rs.item_ref,
            "techCardRef": rs.tech_card_ref or "",
            "profileCode": rs.profile_code,
            "changeReason": rs.change_reason or "",
        })
        for row in rs.rows:
            row_el = ET.SubElement(root, "Row")
            for k, v in row.items():
                row_el.set(k, str(v) if v is not None else "")
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        path.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        with open(path, "ab") as f:
            tree.write(f, encoding="utf-8", xml_declaration=False)
        self.sync_log("export_rs", {"file": str(path), "rows": len(rs.rows)})
        return path


def _try_float(s: Optional[str]) -> Optional[float]:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ============================================================
# HTTP GATEWAY (заглушка для будущей интеграции)
# ============================================================

class HttpGateway(OneCGateway):
    """HTTP-шлюз к 1С:ERP через web-сервис.

    Заглушка. Реальная интеграция — в пилот/продукт.

    Контракт запроса (POST /api/rs):
    Headers:
      Authorization: Basic <base64(user:pass)>
      X-1C-Format: json | xml
    Body: ResourceSpec
    Response: { "ref_1c": "uuid", "status": "ok" | "error", "error": "..." }
    """

    name = "http"
    is_connected = False

    def __init__(self, base_url: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def connect(self) -> bool:
        # Заглушка — реальная интеграция в пилот
        logger.info(f"[HttpGateway] would connect to {self.base_url}")
        self.is_connected = bool(self.base_url)
        return self.is_connected

    def get_nomenclature(self, level=None, parent_ref=None, modified_after=None):
        raise NotImplementedError("HttpGateway — заглушка, будет реализовано в пилот")

    def get_materials(self):
        raise NotImplementedError

    def get_equipment(self):
        raise NotImplementedError

    def get_professions_tariffs(self):
        raise NotImplementedError

    def get_resource_spec(self, ref_1c):
        raise NotImplementedError

    def create_resource_spec(self, rs: OneCResourceSpec) -> str:
        raise NotImplementedError

    def update_resource_spec(self, ref_1c, rs):
        raise NotImplementedError

    def export_to_file(self, rs: OneCResourceSpec, path: Path) -> Path:
        # Используем ту же логику
        return FileGateway().export_to_file(rs, path)


# ============================================================
# FACTORY
# ============================================================

_gateway: Optional[OneCGateway] = None


def get_gateway() -> OneCGateway:
    """Получить активный шлюз. Сейчас всегда FileGateway.

    В будущем: читать из app_settings (gate_type: file | http).
    """
    global _gateway
    if _gateway is None:
        _gateway = FileGateway()
        _gateway.connect()
    return _gateway


def reset_gateway():
    """Сброс (для тестов)."""
    global _gateway
    _gateway = None
