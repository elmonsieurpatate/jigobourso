-- Volumétrie : données synthétiques à prix réalistes (marche aléatoire déterministe), base jetable uniquement.
SET unique_checks=0, foreign_key_checks=0;
INSERT INTO instruments(id,isin,kind,name,country,category)
 SELECT seq, CONCAT('XX',LPAD(seq,10,'0')), IF(seq%4=0,'etf','equity'), CONCAT('Instrument ',seq,' SA'), 'DE', 'Industrials' FROM seq_1_to_20000;
INSERT INTO listings(id,instrument_id,mic,symbol,currency,status,excluded_reason,is_primary)
 SELECT seq, (seq%20000)+1, ELT(1+seq%6,'XETR','XPAR','XLON','XNAS','XNYS','XAMS'), CONCAT('S',seq), 'EUR',
        IF(seq<=5510,'selected','excluded'), IF(seq<=5510,NULL,'liquidité'), IF(seq<=20000,1,0)
 FROM seq_1_to_153000;
SET foreign_key_checks=1;
-- 5510 titres admis × 400 séances (jours ouvrés), prix ~ 5..500, volume entier
INSERT INTO daily_prices(listing_id,price_date,close_px,adj_close_px,volume)
 SELECT l.seq, DATE_SUB('2026-10-27', INTERVAL d.seq DAY),
        ROUND(5+MOD(l.seq*7919,495)+SIN(d.seq/9+l.seq)*3+RAND()*2,6),
        ROUND(5+MOD(l.seq*7919,495)+SIN(d.seq/9+l.seq)*3+RAND()*2,6),
        FLOOR(10000+RAND()*5000000)
 FROM seq_1_to_5510 l JOIN seq_1_to_560 d WHERE WEEKDAY(DATE_SUB('2026-10-27', INTERVAL d.seq DAY)) < 5 AND d.seq<=560;
-- 4500 titres × 20 séances × 30 créneaux de 15 min (moyenne Europe 34 / US 26)
INSERT INTO intraday_prices(listing_id,slot_start,close_px,is_final)
 SELECT l.seq, TIMESTAMP(DATE_SUB('2026-10-27', INTERVAL d.seq DAY),'08:00:00') + INTERVAL (s.seq-1)*15 MINUTE,
        ROUND(5+MOD(l.seq*7919,495)+RAND()*2,6), 1
 FROM seq_1_to_4500 l JOIN seq_1_to_28 d JOIN seq_1_to_30 s
 WHERE WEEKDAY(DATE_SUB('2026-10-27', INTERVAL d.seq DAY)) < 5;
INSERT INTO latest_prices(listing_id,price,price_time,source,currency,avg_volume_3m)
 SELECT seq, 50+MOD(seq,200), '2026-10-27 16:30:00','intraday','EUR',FLOOR(RAND()*5000000) FROM seq_1_to_19842;
INSERT INTO strategy_metrics(listing_id,sessions,slope,slope_log,r2,perf,volatility,drawdown,er,acceleration)
 SELECT l.seq, w.n, RAND(), RAND()/100, RAND(), RAND()*10, RAND()*3, RAND()*20, RAND(), RAND() FROM seq_1_to_5510 l JOIN (SELECT 1 n UNION SELECT 5 UNION SELECT 21 UNION SELECT 63 UNION SELECT 126 UNION SELECT 252 UNION SELECT 10 UNION SELECT 42) w;
INSERT INTO series_state(listing_id,computed_at,last_close_date,closes_count,close_px,ma20,ma50,ma50_prev,daily_change,gap_to_ma20,risk_score)
 SELECT seq, NOW(), '2026-10-27', 400, 50, 49, 48, 47, 0.5, 1.2, 5 FROM seq_1_to_5510;
ANALYZE TABLE daily_prices, intraday_prices, listings, instruments, latest_prices, strategy_metrics, series_state;
