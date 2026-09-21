# -*- coding: utf-8 -*-
"""
Vieclam24h Role Filtering Logic
Enforces strict managerial/director whitelist and individual contributor / entry blacklist.
"""

TOP_MANAGEMENT_KEYWORDS = [
    "trưởng phòng", "truong phong", "truong-phong",
    "giám đốc", "giam doc", "giam-doc",
    "phó phòng", "pho phong", "pho-phong",
    "phó giám đốc", "pho giam doc", "pho-giam-doc",
    "trưởng nhóm", "truong nhom", "truong-nhom",
    "trưởng bộ phận", "truong bo phan", "truong-bo-phan",
    "trưởng ban", "truong ban", "truong-ban",
    "head", "director"
]

GENERAL_MANAGEMENT_KEYWORDS = TOP_MANAGEMENT_KEYWORDS + [
    "quản lý", "quan ly", "quan-ly",
    "chỉ huy", "chi huy", "chi-huy",
    "giám sát", "giam sat", "giam-sat",
    "trưởng", "truong",
    "manager", "lead", "leader", "supervisor"
]

EXCLUDE_KEYWORDS = [
    "nhân viên", "nhan vien", "nhan-vien",
    "chuyên viên", "chuyen vien", "chuyen-vien",
    "thực tập", "thuc tap", "intern",
    "cộng tác viên", "cong tac vien", "cong-tac-vien",
    "học việc", "hoc viec", "hoc-viec"
]

def is_target_management_job(title: str, url: str = "") -> bool:
    if not title and not url:
        return False

    text = f"{title} {url}".lower()
    has_top_mgmt = any(k in text for k in TOP_MANAGEMENT_KEYWORDS)
    has_mgmt = any(k in text for k in GENERAL_MANAGEMENT_KEYWORDS)
    has_excl = any(k in text for k in EXCLUDE_KEYWORDS)

    # If it contains exclusion terms (e.g. nhân viên, chuyên viên),
    # only keep it if it is an explicit top leadership role (e.g. Trưởng phòng quản lý nhân viên)
    if has_excl:
        return has_top_mgmt

    return has_mgmt

def filter_management_jobs(job_list):
    kept = []
    rejected = []
    for job in job_list:
        t = job.get("title", "")
        u = job.get("url", "")
        if is_target_management_job(t, u):
            kept.append(job)
        else:
            rejected.append(job)
    return kept, rejected
