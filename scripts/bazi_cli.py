#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lunar_python import Lunar, Solar

DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_ZI_HOUR_RULE = "split-zi"
GEOCODE_PROVIDER = "open-meteo"
GEOCODE_USER_AGENT = "OpenClaw-BaziSkill/1.0"
CHINA_NAMES = {"", "cn", "china", "中国", "中华人民共和国"}
YANG_STEMS = {"甲", "丙", "戊", "庚", "壬"}
STEM_ELEMENTS = {
    "甲": "木",
    "乙": "木",
    "丙": "火",
    "丁": "火",
    "戊": "土",
    "己": "土",
    "庚": "金",
    "辛": "金",
    "壬": "水",
    "癸": "水",
}
STEM_YIN_YANG = {
    "甲": "阳",
    "乙": "阴",
    "丙": "阳",
    "丁": "阴",
    "戊": "阳",
    "己": "阴",
    "庚": "阳",
    "辛": "阴",
    "壬": "阳",
    "癸": "阴",
}
BRANCH_ELEMENTS = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}
BRANCH_YIN_YANG = {
    "子": "阳",
    "丑": "阴",
    "寅": "阳",
    "卯": "阴",
    "辰": "阳",
    "巳": "阴",
    "午": "阳",
    "未": "阴",
    "申": "阳",
    "酉": "阴",
    "戌": "阳",
    "亥": "阴",
}
HIDDEN_STEMS = {
    "子": [("癸", "本气", 0.6)],
    "丑": [("己", "本气", 0.6), ("癸", "中气", 0.3), ("辛", "余气", 0.1)],
    "寅": [("甲", "本气", 0.6), ("丙", "中气", 0.3), ("戊", "余气", 0.1)],
    "卯": [("乙", "本气", 0.6)],
    "辰": [("戊", "本气", 0.6), ("乙", "中气", 0.3), ("癸", "余气", 0.1)],
    "巳": [("丙", "本气", 0.6), ("庚", "中气", 0.3), ("戊", "余气", 0.1)],
    "午": [("丁", "本气", 0.6), ("己", "中气", 0.3)],
    "未": [("己", "本气", 0.6), ("丁", "中气", 0.3), ("乙", "余气", 0.1)],
    "申": [("庚", "本气", 0.6), ("壬", "中气", 0.3), ("戊", "余气", 0.1)],
    "酉": [("辛", "本气", 0.6)],
    "戌": [("戊", "本气", 0.6), ("辛", "中气", 0.3), ("丁", "余气", 0.1)],
    "亥": [("壬", "本气", 0.6), ("甲", "中气", 0.3)],
}
GENDER_MAP = {
    "male": ("男", 1),
    "man": ("男", 1),
    "m": ("男", 1),
    "男": ("男", 1),
    "1": ("男", 1),
    "female": ("女", 0),
    "woman": ("女", 0),
    "f": ("女", 0),
    "女": ("女", 0),
    "0": ("女", 0),
}
HOUR_BRANCH_MAP = {
    "丑": (1, 30, 0),
    "寅": (3, 30, 0),
    "卯": (5, 30, 0),
    "辰": (7, 30, 0),
    "巳": (9, 30, 0),
    "午": (11, 30, 0),
    "未": (13, 30, 0),
    "申": (15, 30, 0),
    "酉": (17, 30, 0),
    "戌": (19, 30, 0),
    "亥": (21, 30, 0),
}
ZI_SEGMENT_MAP = {
    "night": (23, 30, 0, "夜子时"),
    "late": (23, 30, 0, "夜子时"),
    "晚": (23, 30, 0, "夜子时"),
    "晚子": (23, 30, 0, "夜子时"),
    "night-zi": (23, 30, 0, "夜子时"),
    "early": (0, 30, 0, "早子时"),
    "morning": (0, 30, 0, "早子时"),
    "早": (0, 30, 0, "早子时"),
    "早子": (0, 30, 0, "早子时"),
    "early-zi": (0, 30, 0, "早子时"),
}
ZI_HOUR_RULES = {
    "split-zi": (1, "早晚子时分日"),
    "sect1": (1, "早晚子时分日"),
    "midnight-zi": (2, "子初不换日"),
    "sect2": (2, "子初不换日"),
}


@dataclass
class NormalizedInput:
    calendar_type: str
    timezone: str
    country: str
    city: str
    gender_label: str | None
    gender_code: int | None
    day_rollover_rule: str
    known_time: bool
    civil_dt: datetime
    solar_dt: datetime
    analysis_dt: datetime
    original_time_input: Any
    lunar_input: dict[str, Any] | None
    hour_branch: str | None
    time_note: str | None
    warnings: list[str]
    true_solar_time: dict[str, Any]


def get_timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == DEFAULT_TIMEZONE:
            return timezone(timedelta(hours=8), name=DEFAULT_TIMEZONE)
        if name.upper() == "UTC":
            return timezone.utc
        raise


def parse_datetime_string(value: str) -> dict[str, Any]:
    normalized = value.strip()
    normalized = normalized.replace("T", " ").replace("/", "-")
    normalized = normalized.replace("年", "-").replace("月", "-").replace("日", " ").replace("号", " ")
    normalized = normalized.replace("時", ":").replace("时", ":").replace("點", ":").replace("点", ":")
    normalized = normalized.replace("分", "").replace("秒", "")
    parts = [part for part in normalized.split() if part]
    if not parts:
        raise ValueError("time_input 不能为空")
    date_bits = [int(bit) for bit in parts[0].split("-") if bit]
    if len(date_bits) != 3:
        raise ValueError("日期格式需为 YYYY-MM-DD")
    time_bits = [0, 0, 0]
    has_time = len(parts) > 1
    if has_time:
        raw_time = parts[1]
        tmp = [int(bit) for bit in raw_time.split(":") if bit]
        if len(tmp) >= 1:
            time_bits[0] = tmp[0]
        if len(tmp) >= 2:
            time_bits[1] = tmp[1]
        if len(tmp) >= 3:
            time_bits[2] = tmp[2]
    return {
        "year": date_bits[0],
        "month": date_bits[1],
        "day": date_bits[2],
        "hour": time_bits[0],
        "minute": time_bits[1],
        "second": time_bits[2],
        "has_time": has_time,
    }


def resolve_timezone(payload: dict[str, Any], warnings: list[str]) -> str:
    location = payload.get("location") or {}
    timezone_name = str(payload.get("timezone") or location.get("timezone") or "").strip()
    if timezone_name:
        return timezone_name

    country = str(location.get("country") or "").strip().lower()
    city = str(location.get("city") or "").strip()
    if country in CHINA_NAMES or not country:
        return DEFAULT_TIMEZONE

    warnings.append(f"未提供海外时区，脚本暂按 {DEFAULT_TIMEZONE} 计算。")
    if city:
        warnings.append(f"已收到海外城市 {city}，若要精确排盘请补充 timezone。")
    return DEFAULT_TIMEZONE


def normalize_gender(payload: dict[str, Any], warnings: list[str]) -> tuple[str | None, int | None]:
    raw = payload.get("gender")
    if raw is None or str(raw).strip() == "":
        warnings.append("未提供性别，脚本跳过大运方向与起运计算。")
        return None, None

    normalized = str(raw).strip().lower()
    if normalized not in GENDER_MAP:
        raise ValueError("gender 仅支持 男/女 或 male/female。")
    return GENDER_MAP[normalized]


def parse_longitude(value: Any) -> float:
    if isinstance(value, (int, float)):
        longitude = float(value)
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("longitude 不能为空。")

        sign = -1 if text.startswith("-") or "西" in text or "W" in text.upper() else 1
        numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]
        if not numbers:
            raise ValueError("longitude 格式无效，需提供十进制度数或可解析的经纬度字符串。")

        longitude = numbers[0]
        if len(numbers) >= 2:
            longitude += numbers[1] / 60.0
        if len(numbers) >= 3:
            longitude += numbers[2] / 3600.0
        longitude *= sign

    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude 超出范围，必须位于 -180 到 180 之间。")
    return longitude


def normalize_place_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip())


def strip_cn_admin_suffix(value: str) -> str:
    text = normalize_place_text(value)
    for suffix in ("特别行政区", "自治州", "自治县", "自治区", "地区", "省", "市", "区", "县", "盟"):
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def build_geocode_queries(payload: dict[str, Any]) -> list[str]:
    location = payload.get("location") or {}
    city = normalize_place_text(location.get("city") or payload.get("city") or location.get("name"))
    province = normalize_place_text(location.get("province") or location.get("state") or location.get("admin1"))

    queries: list[str] = []
    for value in (city, strip_cn_admin_suffix(city), province, strip_cn_admin_suffix(province)):
        if value and value not in queries:
            queries.append(value)
    return queries


def fetch_json(url: str) -> Any:
    req = urllib_request.Request(url, headers={"User-Agent": GEOCODE_USER_AGENT})
    with urllib_request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def score_geocode_result(
    result: dict[str, Any],
    query: str,
    province: str,
    country: str,
    timezone_name: str,
) -> float:
    score = 0.0
    query_variants = {normalize_place_text(query), strip_cn_admin_suffix(query)}
    result_name = normalize_place_text(result.get("name"))
    result_admin1 = normalize_place_text(result.get("admin1"))
    result_country = normalize_place_text(result.get("country"))
    result_timezone = str(result.get("timezone") or "")
    feature_code = str(result.get("feature_code") or "")

    if result_name in query_variants or strip_cn_admin_suffix(result_name) in query_variants:
        score += 40.0
    elif any(variant and variant in result_name for variant in query_variants):
        score += 18.0

    province_norm = strip_cn_admin_suffix(province)
    if province_norm:
        if province_norm and province_norm in strip_cn_admin_suffix(result_admin1):
            score += 55.0
        elif result_admin1:
            score -= 10.0

    country_norm = normalize_place_text(country)
    if country_norm:
        if country_norm in result_country:
            score += 25.0
        elif result_country:
            score -= 25.0

    if timezone_name:
        if result_timezone == timezone_name:
            score += 20.0
        elif result_timezone:
            score -= 20.0

    if feature_code.startswith("PPLA") or feature_code == "PPLC":
        score += 15.0
    elif feature_code.startswith("PPL"):
        score += 8.0

    population = result.get("population")
    if isinstance(population, (int, float)) and population > 0:
        score += min(float(population) / 1_000_000.0, 20.0)

    return score


def geocode_longitude(payload: dict[str, Any], timezone_name: str) -> dict[str, Any] | None:
    location = payload.get("location") or {}
    province = normalize_place_text(location.get("province") or location.get("state") or location.get("admin1"))
    country = normalize_place_text(location.get("country") or payload.get("country"))
    best_result: dict[str, Any] | None = None
    best_score = float("-inf")
    best_query = ""

    for query in build_geocode_queries(payload):
        url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib_parse.urlencode(
                {
                    "name": query,
                    "count": 10,
                    "language": "zh",
                    "format": "json",
                }
            )
        )
        try:
            payload_json = fetch_json(url)
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError):
            continue

        results = payload_json.get("results") or []
        for result in results:
            score = score_geocode_result(result, query, province, country, timezone_name)
            if score > best_score:
                best_score = score
                best_result = result
                best_query = query

    if best_result is None or best_score <= 0:
        return None

    return {
        "longitude": float(best_result["longitude"]),
        "latitude": float(best_result["latitude"]),
        "query": best_query,
        "name": best_result.get("name"),
        "admin1": best_result.get("admin1"),
        "country": best_result.get("country"),
        "timezone": best_result.get("timezone"),
        "provider": GEOCODE_PROVIDER,
        "score": best_score,
    }


def resolve_longitude(payload: dict[str, Any]) -> float | None:
    location = payload.get("location") or {}
    for source in (payload, location):
        for key in ("longitude", "lng", "lon"):
            if key in source and source.get(key) not in (None, ""):
                return parse_longitude(source.get(key))
    return None


def normalize_hour_branch(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("时") and len(text) >= 2:
        text = text[:-1]
    if len(text) != 1 or text not in BRANCH_ELEMENTS:
        raise ValueError("hour_branch 仅支持 12 地支，例如 子、丑、寅。")
    return text


def normalize_zi_hour_rule(payload: dict[str, Any]) -> tuple[int, str]:
    raw = str(payload.get("zi_hour_rule") or DEFAULT_ZI_HOUR_RULE).strip().lower()
    if raw not in ZI_HOUR_RULES:
        raise ValueError("zi_hour_rule 仅支持 split-zi 或 midnight-zi。")
    return ZI_HOUR_RULES[raw]


def hour_branch_for_datetime(dt: datetime) -> str:
    total_minutes = dt.hour * 60 + dt.minute + dt.second / 60.0
    if total_minutes >= 23 * 60 or total_minutes < 60:
        return "子"
    branches = ["丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    return branches[int((total_minutes - 60) // 120)]


def equation_of_time_minutes(dt: datetime) -> float:
    day_of_year = dt.timetuple().tm_yday
    days_in_year = 366 if calendar.isleap(dt.year) else 365
    hour_decimal = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    gamma = 2.0 * math.pi / days_in_year * (day_of_year - 1 + (hour_decimal - 12.0) / 24.0)
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def build_true_solar_time(
    payload: dict[str, Any],
    timezone_name: str,
    civil_dt: datetime,
    known_time: bool,
    warnings: list[str],
) -> tuple[datetime, dict[str, Any]]:
    requested = bool(payload.get("use_true_solar_time"))
    base = {
        "requested": requested,
        "applied": False,
        "longitude": None,
        "longitude_source": None,
        "latitude": None,
        "geocode_provider": None,
        "geocode_query": None,
        "geocode_name": None,
        "geocode_admin1": None,
        "geocode_country": None,
        "geocode_timezone": None,
        "civil_ymd_hms": civil_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_ymd_hms": civil_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone_offset_minutes": (civil_dt.utcoffset() or timedelta(0)).total_seconds() / 60.0,
        "standard_offset_minutes": ((civil_dt.utcoffset() or timedelta(0)) - (civil_dt.dst() or timedelta(0))).total_seconds() / 60.0,
        "dst_minutes": (civil_dt.dst() or timedelta(0)).total_seconds() / 60.0,
        "standard_meridian": None,
        "equation_of_time_minutes": None,
        "longitude_correction_minutes": None,
        "total_offset_minutes": None,
    }
    if not requested:
        return civil_dt, base

    if not known_time:
        warnings.append("未提供精确出生时间，真太阳时修正已跳过。")
        return civil_dt, base

    longitude = resolve_longitude(payload)
    source = "input" if longitude is not None else None
    geocode = None
    if longitude is None:
        geocode = geocode_longitude(payload, timezone_name)
        if geocode is None:
            raise ValueError(
                "use_true_solar_time=true 时必须提供 longitude，或至少提供可 geocode 的 location.city/province/country。"
            )
        longitude = geocode["longitude"]
        source = "geocode"

    dst_delta = civil_dt.dst() or timedelta(0)
    offset_delta = civil_dt.utcoffset() or timedelta(0)
    standard_offset_delta = offset_delta - dst_delta
    standard_meridian = standard_offset_delta.total_seconds() / 3600.0 * 15.0
    standard_dt = civil_dt - dst_delta
    eot_minutes = equation_of_time_minutes(standard_dt)
    longitude_minutes = 4.0 * (longitude - standard_meridian)
    dst_minutes = dst_delta.total_seconds() / 60.0
    total_minutes = longitude_minutes + eot_minutes - dst_minutes
    corrected_dt = civil_dt + timedelta(minutes=total_minutes)

    civil_branch = hour_branch_for_datetime(civil_dt)
    corrected_branch = hour_branch_for_datetime(corrected_dt)
    if corrected_dt.date() != civil_dt.date():
        warnings.append(
            f"真太阳时修正使出生日期从 {civil_dt.strftime('%Y-%m-%d')} 调整为 {corrected_dt.strftime('%Y-%m-%d')}，日柱可能因此变化。"
        )
    if corrected_branch != civil_branch:
        warnings.append(f"真太阳时修正使时辰由 {civil_branch} 时变为 {corrected_branch} 时。")

    base.update(
        {
            "applied": True,
            "longitude": longitude,
            "longitude_source": source,
            "corrected_ymd_hms": corrected_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "standard_meridian": standard_meridian,
            "equation_of_time_minutes": eot_minutes,
            "longitude_correction_minutes": longitude_minutes,
            "total_offset_minutes": total_minutes,
        }
    )
    if geocode is not None:
        base.update(
            {
                "latitude": geocode["latitude"],
                "geocode_provider": geocode["provider"],
                "geocode_query": geocode["query"],
                "geocode_name": geocode["name"],
                "geocode_admin1": geocode["admin1"],
                "geocode_country": geocode["country"],
                "geocode_timezone": geocode["timezone"],
            }
        )
        warnings.append(
            f"真太阳时经度来自在线 geocode：{geocode['country'] or ''}{geocode['admin1'] or ''}{geocode['name'] or ''} ({geocode['longitude']:.5f})."
        )
    return corrected_dt, base


def resolve_time_components(
    raw: dict[str, Any],
    payload: dict[str, Any],
    warnings: list[str],
) -> tuple[int, int, int, bool, str | None, str | None]:
    time_unknown = bool(payload.get("time_unknown", False))
    hour_branch = normalize_hour_branch(payload.get("hour_branch") or payload.get("shichen"))
    known_time = bool(raw.get("has_time", False))
    note: str | None = None

    if time_unknown:
        return 12, 0, 0, False, hour_branch, "未提供出生时辰，脚本按 12:00 占位，仅稳定计算年月日柱。"

    if hour_branch and not known_time:
        if hour_branch == "子":
            segment_key = str(payload.get("zi_hour_segment") or "").strip().lower()
            if segment_key not in ZI_SEGMENT_MAP:
                raise ValueError("仅提供子时仍不足以判定日柱，请补充 zi_hour_segment=night|early。")
            hour, minute, second, label = ZI_SEGMENT_MAP[segment_key]
            note = f"按 {label} 代表时刻 {hour:02d}:{minute:02d} 入盘。"
            return hour, minute, second, True, hour_branch, note

        hour, minute, second = HOUR_BRANCH_MAP[hour_branch]
        note = f"仅提供时辰地支，脚本按 {hour:02d}:{minute:02d} 代表时刻入盘。"
        return hour, minute, second, True, hour_branch, note

    if known_time:
        return int(raw["hour"]), int(raw["minute"]), int(raw["second"]), True, hour_branch, None

    warnings.append("未提供出生时间，脚本自动退化为六字模式。")
    return 12, 0, 0, False, hour_branch, "未提供出生时辰，脚本按 12:00 占位，仅稳定计算年月日柱。"


def normalize_time_input(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    original = payload.get("time_input")
    if original is None:
        raise ValueError("缺少 time_input。")

    if isinstance(original, dict):
        raw = {
            "year": int(original["year"]),
            "month": int(original["month"]),
            "day": int(original["day"]),
            "hour": int(original.get("hour", 0)),
            "minute": int(original.get("minute", 0)),
            "second": int(original.get("second", 0)),
            "has_time": any(key in original for key in ("hour", "minute", "second")),
        }
        if "is_leap_month" in original:
            raw["is_leap_month"] = bool(original["is_leap_month"])
    else:
        raw = parse_datetime_string(str(original))

    lunar_input: dict[str, Any] | None = None
    if str(payload.get("calendar_type") or "solar").strip().lower() == "lunar":
        is_leap_month = bool(raw.get("is_leap_month", False) or payload.get("is_leap_month", False) or raw["month"] < 0)
        raw["month"] = abs(int(raw["month"]))
        raw["is_leap_month"] = is_leap_month
        lunar_input = {
            "year": raw["year"],
            "month": raw["month"],
            "day": raw["day"],
            "hour": raw["hour"],
            "minute": raw["minute"],
            "second": raw["second"],
            "is_leap_month": is_leap_month,
        }
    return raw, lunar_input


def normalize_analysis_dt(payload: dict[str, Any], tz, warnings: list[str]) -> datetime:
    raw = payload.get("analysis_date") or payload.get("current_date")
    if raw is None:
        return datetime.now(tz).replace(microsecond=0)

    parsed = parse_datetime_string(str(raw))
    if not parsed["has_time"]:
        warnings.append("analysis_date 未提供时分秒，脚本按 12:00 处理当前分析时刻。")
        parsed["hour"] = 12
    return datetime(
        parsed["year"],
        parsed["month"],
        parsed["day"],
        parsed["hour"],
        parsed["minute"],
        parsed["second"],
        tzinfo=tz,
    )


def normalize_input(payload: dict[str, Any]) -> NormalizedInput:
    warnings: list[str] = []
    timezone_name = resolve_timezone(payload, warnings)
    try:
        tz = get_timezone(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"无法识别时区 {timezone_name}: {exc}") from exc

    calendar_type = str(payload.get("calendar_type") or "solar").strip().lower()
    if calendar_type not in {"solar", "lunar"}:
        raise ValueError("calendar_type 仅支持 solar 或 lunar。")

    raw, lunar_input = normalize_time_input(payload)
    hour, minute, second, known_time, hour_branch, time_note = resolve_time_components(raw, payload, warnings)
    raw["hour"] = hour
    raw["minute"] = minute
    raw["second"] = second

    gender_label, gender_code = normalize_gender(payload, warnings)
    _, rule_label = normalize_zi_hour_rule(payload)

    if calendar_type == "solar":
        civil_dt = datetime(raw["year"], raw["month"], raw["day"], hour, minute, second, tzinfo=tz)
    else:
        lunar_month = -raw["month"] if bool(raw.get("is_leap_month", False)) else raw["month"]
        lunar_obj = Lunar.fromYmdHms(raw["year"], lunar_month, raw["day"], hour, minute, second)
        solar_obj = lunar_obj.getSolar()
        civil_dt = datetime(
            solar_obj.getYear(),
            solar_obj.getMonth(),
            solar_obj.getDay(),
            solar_obj.getHour(),
            solar_obj.getMinute(),
            solar_obj.getSecond(),
            tzinfo=tz,
        )

    analysis_dt = normalize_analysis_dt(payload, tz, warnings)
    location = payload.get("location") or {}
    solar_dt, true_solar_time = build_true_solar_time(payload, timezone_name, civil_dt, known_time, warnings)
    if payload.get("use_true_solar_time") and hour_branch and not raw.get("has_time", False):
        warnings.append("真太阳时修正基于时辰代表时刻完成；若接近时辰边界，请尽量补充精确钟点。")

    return NormalizedInput(
        calendar_type=calendar_type,
        timezone=timezone_name,
        country=str(location.get("country") or "").strip(),
        city=str(location.get("city") or "").strip(),
        gender_label=gender_label,
        gender_code=gender_code,
        day_rollover_rule=rule_label,
        known_time=known_time,
        civil_dt=civil_dt,
        solar_dt=solar_dt,
        analysis_dt=analysis_dt,
        original_time_input=payload.get("time_input"),
        lunar_input=lunar_input,
        hour_branch=hour_branch,
        time_note=time_note,
        warnings=warnings,
        true_solar_time=true_solar_time,
    )


def build_solar_and_lunar(normalized: NormalizedInput) -> tuple[Solar, Any, Any]:
    solar = Solar.fromYmdHms(
        normalized.solar_dt.year,
        normalized.solar_dt.month,
        normalized.solar_dt.day,
        normalized.solar_dt.hour,
        normalized.solar_dt.minute,
        normalized.solar_dt.second,
    )
    lunar = solar.getLunar()
    eight_char = lunar.getEightChar()
    sect = 1 if normalized.day_rollover_rule == "早晚子时分日" else 2
    eight_char.setSect(sect)
    return solar, lunar, eight_char


def serialize_datetime(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def serialize_solar(solar: Solar, timezone_name: str) -> dict[str, Any]:
    return {
        "year": solar.getYear(),
        "month": solar.getMonth(),
        "day": solar.getDay(),
        "hour": solar.getHour(),
        "minute": solar.getMinute(),
        "second": solar.getSecond(),
        "ymd_hms": solar.toYmdHms(),
        "timezone": timezone_name,
    }


def serialize_lunar(lunar: Any) -> dict[str, Any]:
    return {
        "year": lunar.getYear(),
        "month": abs(lunar.getMonth()),
        "day": lunar.getDay(),
        "is_leap_month": lunar.getMonth() < 0,
        "month_text": lunar.getMonthInChinese(),
        "day_text": lunar.getDayInChinese(),
        "year_ganzhi": lunar.getYearInGanZhi(),
        "month_ganzhi": lunar.getMonthInGanZhi(),
        "day_ganzhi": lunar.getDayInGanZhi(),
        "time_ganzhi": lunar.getTimeInGanZhi(),
    }


def serialize_jieqi(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "name": node.getName(),
        "solar": node.getSolar().toYmdHms(),
    }


def build_hidden_stems(branch: str, branch_ten_gods: list[str]) -> list[dict[str, Any]]:
    hidden = HIDDEN_STEMS.get(branch, [])
    entries: list[dict[str, Any]] = []
    for idx, (stem, layer, weight) in enumerate(hidden):
        entries.append(
            {
                "stem": stem,
                "layer": layer,
                "weight": weight,
                "element": STEM_ELEMENTS[stem],
                "yin_yang": STEM_YIN_YANG[stem],
                "ten_god": branch_ten_gods[idx] if idx < len(branch_ten_gods) else None,
            }
        )
    return entries


def build_pillar(eight_char: Any, prefix: str) -> dict[str, Any]:
    gan_zhi = getattr(eight_char, f"get{prefix}")()
    stem = getattr(eight_char, f"get{prefix}Gan")()
    branch = getattr(eight_char, f"get{prefix}Zhi")()
    branch_ten_gods = list(getattr(eight_char, f"get{prefix}ShiShenZhi")())
    return {
        "gan_zhi": gan_zhi,
        "stem": stem,
        "branch": branch,
        "stem_yin_yang": STEM_YIN_YANG[stem],
        "branch_yin_yang": BRANCH_YIN_YANG[branch],
        "stem_element": STEM_ELEMENTS[stem],
        "branch_element": BRANCH_ELEMENTS[branch],
        "wu_xing": getattr(eight_char, f"get{prefix}WuXing")(),
        "na_yin": getattr(eight_char, f"get{prefix}NaYin")(),
        "shi_shen_gan": getattr(eight_char, f"get{prefix}ShiShenGan")(),
        "shi_shen_zhi": branch_ten_gods,
        "di_shi": getattr(eight_char, f"get{prefix}DiShi")(),
        "xun": getattr(eight_char, f"get{prefix}Xun")(),
        "xun_kong": getattr(eight_char, f"get{prefix}XunKong")(),
        "hidden_stems": build_hidden_stems(branch, branch_ten_gods),
    }


def shift_years(dt: datetime, years: int) -> datetime:
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        return dt.replace(month=2, day=28, year=dt.year + years)


def compute_age_years(birth_dt: datetime, analysis_dt: datetime) -> int:
    years = analysis_dt.year - birth_dt.year
    if (analysis_dt.month, analysis_dt.day) < (birth_dt.month, birth_dt.day):
        years -= 1
    return years


def is_forward_luck(year_stem: str, gender_label: str | None) -> bool | None:
    if gender_label is None:
        return None
    return (year_stem in YANG_STEMS and gender_label == "男") or (year_stem not in YANG_STEMS and gender_label == "女")


def build_luck(
    normalized: NormalizedInput,
    eight_char: Any,
    analysis_dt: datetime,
    month_pillar: str,
) -> dict[str, Any]:
    if normalized.gender_code is None or normalized.gender_label is None:
        return {
            "available": False,
            "reason": "缺少 gender，未计算大运。",
        }

    yun = eight_char.getYun(normalized.gender_code)
    first_start_solar = yun.getStartSolar()
    first_start_dt = datetime(
        first_start_solar.getYear(),
        first_start_solar.getMonth(),
        first_start_solar.getDay(),
        first_start_solar.getHour(),
        first_start_solar.getMinute(),
        first_start_solar.getSecond(),
        tzinfo=normalized.solar_dt.tzinfo,
    )
    forward = is_forward_luck(eight_char.getYearGan(), normalized.gender_label)

    raw_da_yun = list(yun.getDaYun())
    da_yun_entries: list[dict[str, Any]] = []
    active_index: int | None = None
    total = len(raw_da_yun)

    for raw in raw_da_yun:
        idx = raw.getIndex()
        if idx == 0:
            start_dt = normalized.solar_dt
            end_dt = first_start_dt - timedelta(seconds=1)
            gan_zhi = month_pillar
            label = "起运前"
        else:
            start_dt = shift_years(first_start_dt, (idx - 1) * 10)
            end_dt = None if idx == total - 1 else shift_years(first_start_dt, idx * 10) - timedelta(seconds=1)
            gan_zhi = raw.getGanZhi()
            label = f"第{idx}步"

        entry = {
            "index": idx,
            "label": label,
            "gan_zhi": gan_zhi,
            "start_age": raw.getStartAge(),
            "end_age": raw.getEndAge(),
            "start_year": raw.getStartYear(),
            "end_year": raw.getEndYear(),
            "start_solar": serialize_datetime(start_dt),
            "end_solar": serialize_datetime(end_dt),
        }
        da_yun_entries.append(entry)

        in_range = analysis_dt >= start_dt and (end_dt is None or analysis_dt <= end_dt)
        if in_range:
            active_index = idx

    if active_index is None and da_yun_entries:
        active_index = da_yun_entries[-1]["index"]

    active_da_yun = next((entry for entry in da_yun_entries if entry["index"] == active_index), None)
    active_liu_nian = None
    if active_index is not None:
        for liu_nian in raw_da_yun[active_index].getLiuNian():
            if liu_nian.getYear() == analysis_dt.year:
                active_liu_nian = {
                    "year": liu_nian.getYear(),
                    "gan_zhi": liu_nian.getGanZhi(),
                    "age": liu_nian.getAge(),
                }
                break

    return {
        "available": True,
        "direction": "顺排" if forward else "逆排",
        "start_offset": {
            "years": yun.getStartYear(),
            "months": yun.getStartMonth(),
            "days": yun.getStartDay(),
        },
        "start_solar": first_start_solar.toYmdHms(),
        "da_yun": da_yun_entries,
        "current": {
            "analysis_solar": serialize_datetime(analysis_dt),
            "analysis_age": compute_age_years(normalized.civil_dt, analysis_dt),
            "active_da_yun": active_da_yun,
            "active_liu_nian": active_liu_nian,
        },
    }


def build_output(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_input(payload)
    solar, lunar, eight_char = build_solar_and_lunar(normalized)

    prev_jie = lunar.getPrevJie()
    next_jie = lunar.getNextJie()
    analysis_solar = Solar.fromYmdHms(
        normalized.analysis_dt.year,
        normalized.analysis_dt.month,
        normalized.analysis_dt.day,
        normalized.analysis_dt.hour,
        normalized.analysis_dt.minute,
        normalized.analysis_dt.second,
    )

    pillars = {
        "year": build_pillar(eight_char, "Year"),
        "month": build_pillar(eight_char, "Month"),
        "day": build_pillar(eight_char, "Day"),
        "time": build_pillar(eight_char, "Time") if normalized.known_time else None,
    }

    warnings = list(normalized.warnings)
    if normalized.known_time and normalized.hour_branch:
        warnings.append(f"输入使用时辰地支 {normalized.hour_branch}，请注意这不是精确钟点。")

    if normalized.timezone != DEFAULT_TIMEZONE:
        warnings.append(f"脚本按 {normalized.timezone} 的本地时钟计算。")

    luck = build_luck(normalized, eight_char, normalized.analysis_dt, pillars["month"]["gan_zhi"])

    return {
        "normalized_input": {
            "calendar_type": normalized.calendar_type,
            "timezone": normalized.timezone,
            "country": normalized.country,
            "city": normalized.city,
            "gender": normalized.gender_label,
            "day_rollover_rule": normalized.day_rollover_rule,
            "known_time": normalized.known_time,
            "hour_branch": normalized.hour_branch,
            "original_time_input": normalized.original_time_input,
            "analysis_date": serialize_datetime(normalized.analysis_dt),
        },
        "calendar": {
            "solar": serialize_solar(solar, normalized.timezone),
            "lunar": serialize_lunar(lunar),
            "jieqi": {
                "prev_jie": serialize_jieqi(prev_jie),
                "next_jie": serialize_jieqi(next_jie),
            },
        },
        "bazi": {
            "pillars": pillars,
            "day_master": {
                "stem": eight_char.getDayGan(),
                "element": STEM_ELEMENTS[eight_char.getDayGan()],
                "yin_yang": STEM_YIN_YANG[eight_char.getDayGan()],
            },
            "special": {
                "tai_yuan": eight_char.getTaiYuan(),
                "tai_yuan_na_yin": eight_char.getTaiYuanNaYin(),
                "tai_xi": eight_char.getTaiXi(),
                "tai_xi_na_yin": eight_char.getTaiXiNaYin(),
                "ming_gong": eight_char.getMingGong(),
                "ming_gong_na_yin": eight_char.getMingGongNaYin(),
                "shen_gong": eight_char.getShenGong(),
                "shen_gong_na_yin": eight_char.getShenGongNaYin(),
            },
        },
        "luck": luck,
        "analysis_context": {
            "analysis_solar": analysis_solar.toYmdHms(),
            "analysis_year_ganzhi": analysis_solar.getLunar().getYearInGanZhi(),
        },
        "true_solar_time": normalized.true_solar_time,
        "notes": {
            "time_note": normalized.time_note,
            "true_solar_time_applied": normalized.true_solar_time["applied"],
        },
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a structured bazi chart payload.")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", required=True, help="Path to output JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        output = build_output(payload)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        error_payload = {"error": str(exc)}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
