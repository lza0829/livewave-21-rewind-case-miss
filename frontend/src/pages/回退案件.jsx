import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 回退案件() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [结案果, 设结案果] = useState(null);
  const reload = () => {
    取("/核证/回退案件").then(setRows).catch((e) => setErr(String(e.message || e)));
  };
  useEffect(() => { reload(); }, []);
  const 做结案 = async (房间键, 案件号) => {
    设结案果(await 递("/回退案件/结案", { 房间键, 案件号 }));
    reload();
  };
  return (
    <div>
      <h1 className="题">回退案件核证</h1>
      <p className="述">
        只读核证：案件簿 ↔ 水位线 ↔ 关窗表对齐核验。口径<strong>未结案件封锁</strong>——
        同房未结案件至多一笔，存在未结案件则该房新的变小写整票拒绝；结案按房间键+案件号双重定位，邻房不得串改。
      </p>
      {err && <pre className="码">{err}</pre>}
      <button className="次" onClick={reload}>刷新</button>
      {rows && (
        <div className="行" style={{ gap: "0.7rem" }}>
          <span className={`徽章 ${rows.valid ? "通" : "败"}`}>{rows.valid ? "对齐" : "失齐"}</span>
          <span className="讯" style={{ margin: 0 }}>
            未结封锁：{rows.未结封锁 ? `是（${(rows.封锁房间 || []).join("、")}）` : "否"}
          </span>
        </div>
      )}
      {rows?.失齐?.length > 0 && (
        <div className="报箱 码">{rows.失齐.join("\n")}</div>
      )}
      {rows?.未结案件?.length > 0 && (
        <div className="段">
          <div className="段题">未结案件</div>
          <table>
            <thead>
              <tr><th>案件号</th><th>房间</th><th>旧水位</th><th>请求值</th><th>处置态</th><th></th></tr>
            </thead>
            <tbody>
              {rows.未结案件.map((a) => (
                <tr key={a.编号}>
                  <td className="码">{a.案件号}</td>
                  <td>{a.房间键}</td>
                  <td className="码">{a.旧水位}</td>
                  <td className="码">{a.请求值}</td>
                  <td>{a.处置态}</td>
                  <td><button className="次" onClick={() => 做结案(a.房间键, a.案件号)}>结案</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {结案果 && <div className="报箱 码">{JSON.stringify(结案果, null, 2)}</div>}
      <div className="段">
        <div className="段题">案件簿（近 50 笔）</div>
        {!rows?.案件?.length ? (
          <div className="空态">案件簿为空</div>
        ) : (
          <table>
            <thead>
              <tr><th>案件号</th><th>房间</th><th>旧水位</th><th>请求值</th><th>处置态</th><th>前案</th><th>时刻</th><th>结案时刻</th></tr>
            </thead>
            <tbody>
              {rows.案件.map((a) => (
                <tr key={a.编号}>
                  <td className="码">{a.案件号}</td>
                  <td>{a.房间键}</td>
                  <td className="码">{a.旧水位}</td>
                  <td className="码">{a.请求值}</td>
                  <td><span className={`徽章 ${a.处置态 === "未结" ? "败" : "通"}`}>{a.处置态}</span></td>
                  <td className="码">{a.前案案件号 || "—"}</td>
                  <td className="码">{a.时刻}</td>
                  <td className="码">{a.结案时刻 || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
