import React, { useEffect, useState } from "react";
import { 取, 递 } from "../api.js";

export default function 水位回退页() {
  const [房, 设房] = useState([]);
  const [房间键, 设房间键] = useState("房A");
  const [新值, 设新值] = useState("2026-11-22T12:00:30Z");
  const [审查, 设审查] = useState(null);
  const [结果, 设结果] = useState(null);
  const [事, 设事] = useState(null);

  const 刷房 = () => 取("/直播间").then((xs) => { 设房(xs); if (xs[0]) 设房间键((k) => k || xs[0].房间键); });
  useEffect(() => { 刷房(); }, []);

  const 做审查 = async () => {
    设审查(null);
    设审查(await 取(`/水位变小/审查?房间键=${encodeURIComponent(房间键)}&新值=${encodeURIComponent(新值)}`));
  };
  const 做提交 = async () => {
    设结果(null);
    设结果(await 递("/水位变小", { 房间键, 新值 }));
    刷房();
  };
  const 抬升窗 = async () => {
    设事(await 递("/装载/夹具?名=" + encodeURIComponent("水位回退样例")));
    刷房();
  };

  const 当前 = 房.find((r) => r.房间键 === 房间键)?.水位线?.事件时水位 || "—";

  return (
    <div>
      <h1 className="题">水位回退禁改</h1>
      <p className="述">
        全局口径<strong>禁止变小</strong>：任何把水位改小的请求整票拒绝——水位不变、已关闭窗保持关闭、旁路界不变。
        审查是只读裁决；提交是写闸，拒绝时整票回滚，水位与窗态一个字节都不动。
      </p>
      <div className="提示条">
        夹具：先推「水位回退样例」（抬水位并关窗），再提交更小值——水位保持旧值，已关窗仍关闭。
      </div>
      <div className="行">
        <button className="水" onClick={抬升窗}>① 推夹具抬水位并关窗</button>
        <button className="次" onClick={刷房}>刷新水位</button>
      </div>
      {事 && (
        <div className="报箱 码">
          {`入窗 ${事.入窗} · 新关窗 ${事.新关窗}\n`}
        </div>
      )}
      <div className="段">
        <div className="段题">水位变小请求</div>
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
          <button className="水" onClick={做提交}>提交写闸</button>
        </div>
        {审查 && (
          <div className="报箱 码">{JSON.stringify(审查, null, 2)}</div>
        )}
        {结果 && (
          <div className="报箱 码">{JSON.stringify(结果, null, 2)}</div>
        )}
      </div>
    </div>
  );
}
