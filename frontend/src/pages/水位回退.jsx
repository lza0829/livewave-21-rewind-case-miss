import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 水位回退页() {
  const [房, 设房] = useState([]);
  const [房间键, 设房间键] = useState("房A");
  const [新值, 设新值] = useState("2026-11-22T12:00:30Z");
  const [审查, 设审查] = useState(null);
  const [结果, 设结果] = useState(null);
  const [事, 设事] = useState(null);
  const [核证, 设核证] = useState(null);
  const [结案果, 设结案果] = useState(null);

  const 刷房 = () => 取("/直播间").then((xs) => { 设房(xs); if (xs[0]) 设房间键((k) => k || xs[0].房间键); });
  const 刷核证 = (k) => 取(`/核证/回退案件?房间键=${encodeURIComponent(k ?? 房间键)}`).then(设核证);
  useEffect(() => { 刷房(); }, []);
  useEffect(() => { if (房间键) 刷核证(房间键); }, [房间键]);

  const 做审查 = async () => {
    设审查(null);
    设审查(await 取(`/水位变小/审查?房间键=${encodeURIComponent(房间键)}&新值=${encodeURIComponent(新值)}`));
  };
  const 做提交 = async () => {
    设结果(null);
    设结案果(null);
    设结果(await 递("/水位变小", { 房间键, 新值 }));
    刷房();
    刷核证();
  };
  const 做结案 = async () => {
    设结案果(null);
    const 案件号 = 核证?.未结案件?.[0]?.案件号;
    if (!案件号) return;
    设结案果(await 递("/回退案件/结案", { 房间键, 案件号 }));
    刷核证();
  };
  const 抬升窗 = async () => {
    设事(await 递("/装载/夹具?名=" + encodeURIComponent("水位回退样例")));
    刷房();
    刷核证();
  };

  const 当前 = 房.find((r) => r.房间键 === 房间键)?.水位线?.事件时水位 || "—";

  return (
    <div>
      <h1 className="题">水位回退 · 回退案件</h1>
      <p className="述">
        全局口径<strong>未结案件封锁</strong>：变小写是「处置」——处置成功同票落回退案件
        （房间、旧水位、请求值、处置态、案件号），并同票降水位、重开窗止高于新值的已关闭窗。
        同房有未结案件时新的变小写<strong>整票拒绝</strong>，只能先结案；半截失败整票回滚。
      </p>
      <div className="提示条">
        夹具：先推「水位回退样例」（抬水位并关窗）→ 提交变小值（处置落案、同票重开窗）→
        未结案再交更小值（整票拒绝、数值不降）→ 结案后才可再处置。
      </div>
      <div className="行">
        <button className="水" onClick={抬升窗}>① 推夹具抬水位并关窗</button>
        <button className="次" onClick={() => { 刷房(); 刷核证(); }}>刷新水位</button>
      </div>
      {事 && (
        <div className="报箱 码">
          {`入窗 ${事.入窗} · 新关窗 ${事.新关窗}\n`}
        </div>
      )}
      <div className="段">
        <div className="段题">水位变小处置</div>
        <div className="行">
          <label>房间
            <select value={房间键} onChange={(e) => 设房间键(e.target.value)}>
              {房.map((r) => <option key={r.房间键} value={r.房间键}>{r.房间键}</option>)}
            </select>
          </label>
          <label>新值 <input className="码" value={新值} onChange={(e) => 设新值(e.target.value)} /></label>
          <span className="讯" style={{ margin: 0 }}>当前水位：{当前}</span>
        </div>
        <div className="行">
          <button className="次" onClick={做审查}>只读审查</button>
          <button className="水" onClick={做提交}>提交处置</button>
          <button className="次" disabled={!核证?.未结封锁} onClick={做结案}>
            结案{核证?.未结案件?.[0]?.案件号 ? `（${核证.未结案件[0].案件号}）` : ""}
          </button>
          {核证 && (
            <span className={`徽章 ${核证.未结封锁 ? "败" : "通"}`}>
              {核证.未结封锁 ? "未结封锁中" : "可直接变小"}
            </span>
          )}
        </div>
        {审查 && (
          <div className="报箱 码">{JSON.stringify(审查, null, 2)}</div>
        )}
        {结果 && (
          <div className="报箱 码">{JSON.stringify(结果, null, 2)}</div>
        )}
        {结案果 && (
          <div className="报箱 码">{JSON.stringify(结案果, null, 2)}</div>
        )}
      </div>
    </div>
  );
}
