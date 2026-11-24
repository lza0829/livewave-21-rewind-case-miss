"""回退案件（已实现 · 架构甲「未结案件封锁」）

全局只贯彻一种口径：**未结案件封锁**。
- 变小写是「处置」：处置成功必须在同一事务内落一笔回退案件
  （房间键、旧水位、请求值、处置态、案件号，并挂前案案件号作案件上下文）。
- 同房存在未结案件时，新的变小写整票拒绝，只能先结案；不采用案件链续裁口径。
- 结案按 房间键+案件号 双重定位，邻房案件不得结本房的案、更不得串改本房水位。

本模块只依赖 conn 操作；写路径的入口在 app/services/水位闸.py（同票立案+降水位+重开窗）。
"""
状态 = "已实现"
口径 = "未结案件封锁"
只读接口 = "GET /api/核证/回退案件?房间键="
结案接口 = "POST /api/回退案件/结案"

未结 = "未结"
已结 = "已结"


def 未结案(conn, 房间键: str):
    """该房当前未结的回退案件（甲口径下至多一笔）；无则 None。"""
    return conn.execute(
        "SELECT * FROM 回退案件 WHERE 房间键=? AND 处置态=? ORDER BY 编号 DESC LIMIT 1",
        (房间键, 未结),
    ).fetchone()


def 应封锁变小(conn, 房间键: str) -> bool:
    """甲「未结案件封锁」：存在未结案件则新的变小写整票拒绝。"""
    return 未结案(conn, 房间键) is not None


def 立案(conn, 房间键: str, 旧水位: str, 请求值: str, 时刻: str) -> dict:
    """同事务内立案。返回落盘后的案件（含案件号、前案案件号）。

    调用方须已处于 BEGIN IMMEDIATE 事务中；失败随调用方整票回滚。
    """
    前案 = conn.execute(
        "SELECT 案件号 FROM 回退案件 WHERE 房间键=? ORDER BY 编号 DESC LIMIT 1",
        (房间键,),
    ).fetchone()
    前案号 = 前案["案件号"] if 前案 else ""
    cur = conn.execute(
        """INSERT INTO 回退案件(房间键, 旧水位, 请求值, 处置态, 案件号, 时刻, 前案案件号)
           VALUES (?,?,?,?,?,?,?)""",
        (房间键, 旧水位, 请求值, 未结, "", 时刻, 前案号),
    )
    编号 = cur.lastrowid
    案件号 = f"案-{房间键}-{编号:04d}"
    conn.execute("UPDATE 回退案件 SET 案件号=? WHERE 编号=?", (案件号, 编号))
    return {
        "编号": 编号,
        "房间键": 房间键,
        "旧水位": 旧水位,
        "请求值": 请求值,
        "处置态": 未结,
        "案件号": 案件号,
        "前案案件号": 前案号,
        "时刻": 时刻,
    }


def 结案(conn, 房间键: str, 案件号: str, 时刻: str) -> dict:
    """结案：按 房间键+案件号 双重定位，禁止邻房案件串改本房。

    调用方须已处于 BEGIN IMMEDIATE 事务中。
    """
    行 = conn.execute(
        "SELECT * FROM 回退案件 WHERE 案件号=?", (案件号,)
    ).fetchone()
    if not 行:
        return {"valid": False, "案件号": 案件号, "房间键": 房间键, "理由": "案件号不存在"}
    if 行["房间键"] != 房间键:
        return {
            "valid": False,
            "案件号": 案件号,
            "房间键": 房间键,
            "理由": f"案件属房间{行['房间键']}，不得由{房间键}结案（禁止邻房串改）",
        }
    if 行["处置态"] == 已结:
        return {
            "valid": True,
            "案件号": 案件号,
            "房间键": 房间键,
            "处置态": 已结,
            "理由": "案件本已结（幂等）",
            "已落盘": False,
        }
    conn.execute(
        "UPDATE 回退案件 SET 处置态=?, 结案时刻=? WHERE 编号=?",
        (已结, 时刻, 行["编号"]),
    )
    return {
        "valid": True,
        "案件号": 案件号,
        "房间键": 房间键,
        "处置态": 已结,
        "理由": "已结案，本房可再处置",
        "已落盘": True,
    }


def 核证失齐(conn, 房间键: str | None = None) -> list:
    """案件簿 ↔ 水位线 ↔ 关窗表 的对齐核验（只读）。返回问题列表，空为对齐。"""
    问题 = []
    参 = (房间键,) if 房间键 else ()
    房滤 = " AND 房间键=?" if 房间键 else ""

    # ① 案件号不得为空（禁止无案件号的处置记录）
    for r in conn.execute(
        f"SELECT 编号, 房间键 FROM 回退案件 WHERE 案件号=''{房滤}", 参
    ).fetchall():
        问题.append(f"案件{r['编号']}({r['房间键']})案件号为空")

    # ② 同房未结案件至多一笔（甲口径封锁唯一性）
    for r in conn.execute(
        f"""SELECT 房间键, COUNT(*) AS c FROM 回退案件
            WHERE 处置态='{未结}'{房滤}
            GROUP BY 房间键 HAVING c>1""",
        参,
    ).fetchall():
        问题.append(f"{r['房间键']}未结案件{r['c']}笔，违反未结案件封锁唯一性")

    # ③ 每房最新案件的请求值不得高于当前水位——否则水位被无案件的变小改小过
    q = f"""SELECT c.房间键, c.请求值, c.案件号, w.事件时水位
            FROM 回退案件 c
            JOIN (SELECT 房间键, MAX(编号) AS 最新 FROM 回退案件 GROUP BY 房间键) t
              ON t.最新 = c.编号
            JOIN 水位线 w ON w.房间键 = c.房间键
            {('WHERE c.房间键=?') if 房间键 else ''}"""
    from app.services import 时间

    for r in conn.execute(q, 参).fetchall():
        if 时间.解析(r["事件时水位"]) < 时间.解析(r["请求值"]):
            问题.append(
                f"{r['房间键']}水位{r['事件时水位']}低于最近案件{r['案件号']}请求值{r['请求值']}：存在未挂案件的变小"
            )

    # ④ 关窗表/热度窗与水位对齐（复用水位闸不变式）
    from app.services import 水位闸

    问题.extend(水位闸.不变式(conn, 房间键))
    return 问题


def 查案件(conn, 房间键: str | None = None) -> dict:
    """回退案件核证只读接口：案件簿 + 未结封锁 + 与水位闸/关窗表/热度窗的对齐核验。"""
    q = "SELECT * FROM 回退案件"
    args: tuple = ()
    if 房间键:
        q += " WHERE 房间键=?"
        args = (房间键,)
    q += " ORDER BY 编号 DESC LIMIT 50"
    案件 = [dict(r) for r in conn.execute(q, args)]

    if 房间键:
        未结案件 = [dict(r) for r in conn.execute(
            "SELECT * FROM 回退案件 WHERE 房间键=? AND 处置态=? ORDER BY 编号 DESC",
            (房间键, 未结),
        )]
    else:
        未结案件 = [dict(r) for r in conn.execute(
            "SELECT * FROM 回退案件 WHERE 处置态=? ORDER BY 编号 DESC", (未结,)
        )]
    失齐 = 核证失齐(conn, 房间键)
    封锁 = bool(未结案件)
    return {
        "口径": 口径,
        "案件": 案件,
        "未结案件": 未结案件,
        "封锁房间": sorted({r["房间键"] for r in 未结案件}),
        "未结封锁": 封锁,
        "可直接变小": not 封锁,
        "失齐": 失齐,
        "valid": not 失齐,
    }
