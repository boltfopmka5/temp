import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, List
import warnings
import os
import sys
import time
import struct
import wave
import subprocess
from datetime import datetime, timedelta

# Для звуковых сигналов Windows
import winsound

warnings.filterwarnings('ignore')

# ----------------------------------------------------------------------------
# Создаем директорию для звуков
SOUNDS_DIR = "sounds"
if not os.path.exists(SOUNDS_DIR):
    os.makedirs(SOUNDS_DIR)


# ============================================================================
# СИСТЕМА ЗВУКОВЫХ СИГНАЛОВ И УВЕДОМЛЕНИЙ
class AlertSystem:
    """
    Система оповещений для Windows 10/11:
    - Звуковые сигналы через winsound + wave (встроенные модули)
    - Всплывающие уведомления через PowerShell (встроен в Windows)
    - Запись в лог
    """

    def __init__(self):
        self.last_alert_time = {}
        self.alert_cooldown = 60
        self.notification_enabled = self._check_powershell()
        self._generate_sound_files()
    
    def _check_powershell(self) -> bool:
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Write-Host 'test'"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False
        
    def _generate_sound_files(self):
        sound_configs = {
            "strong_buy.wav": ([800, 1000, 1200], 0.15, "STRONG BUY"),
            "strong_sell.wav": ([1200, 1000, 800], 0.15, "STRONG SELL"),
            "buy.wav": ([1000, 1200], 0.1, "BUY"),
            "sell.wav": ([1000, 800], 0.1, "SELL"),
            "alert.wav": ([600, 800, 1000, 800, 600], 0.12, "ALERT")
        }
        
        for filename, (frequencies, duration, name) in sound_configs.items():
            filepath = os.path.join(SOUNDS_DIR, filename)
            if not os.path.exists(filepath):
                if self._create_tone_wav(filepath, frequencies, duration):
                    print(f"[OK] Создан звуковой файл: {name} ({filename})")
    
    def _create_tone_wav(self, filename: str, frequencies: List[int], duration: float) -> bool:
        try:
            sample_rate = 44100
            samples_per_tone = int(sample_rate * duration)
            total_samples = samples_per_tone * len(frequencies)
            
            signal = np.zeros(total_samples, dtype=np.float64)
            
            for i, freq in enumerate(frequencies):
                start = i * samples_per_tone
                end = (i + 1) * samples_per_tone
                t = np.linspace(0, duration, samples_per_tone, endpoint=False)
                envelope = np.exp(-3 * t / duration)
                tone = np.sin(2 * np.pi * freq * t) * envelope * 0.6
                signal[start:end] = tone
            
            max_val = np.max(np.abs(signal))
            if max_val > 0:
                signal = signal / max_val * 0.8
            
            signal_int = (signal * 32767).astype(np.int16)
            
            with wave.open(filename, 'w') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(signal_int.tobytes())
            
            return True
        except Exception as e:
            print(f"[WARNING] Ошибка создания звукового файла {filename}: {e}")
            return False
    
    def play_sound_file(self, filename: str):
        try:
            if os.path.exists(filename):
                winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return True
        except Exception as e:
            print(f"[WARNING] Ошибка воспроизведения {filename}: {e}")
        return False
    
    def play_system_beep(self, signal_type: int):
        try:
            if signal_type == 2:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                time.sleep(0.05)
                winsound.Beep(800, 120)
                time.sleep(0.03)
                winsound.Beep(1000, 120)
                time.sleep(0.03)
                winsound.Beep(1200, 200)
            elif signal_type == -2:
                winsound.MessageBeep(winsound.MB_ICONHAND)
                time.sleep(0.05)
                winsound.Beep(1200, 120)
                time.sleep(0.03)
                winsound.Beep(1000, 120)
                time.sleep(0.03)
                winsound.Beep(800, 200)
            elif signal_type == 1:
                winsound.Beep(1000, 100)
                time.sleep(0.03)
                winsound.Beep(1200, 150)
            elif signal_type == -1:
                winsound.Beep(1000, 100)
                time.sleep(0.03)
                winsound.Beep(800, 150)
            else:
                winsound.Beep(800, 200)
        except Exception as e:
            print(f"[WARNING] Ошибка системного звука: {e}")
    
    def play_sound(self, signal_type: int):
        sound_files = {
            2: os.path.join(SOUNDS_DIR, "strong_buy.wav"),
            -2: os.path.join(SOUNDS_DIR, "strong_sell.wav"),
            1: os.path.join(SOUNDS_DIR, "buy.wav"),
            -1: os.path.join(SOUNDS_DIR, "sell.wav"),
            0: os.path.join(SOUNDS_DIR, "alert.wav")
        }
        
        filename = sound_files.get(signal_type)
        if filename and os.path.exists(filename):
            if self.play_sound_file(filename):
                return
        
        self.play_system_beep(signal_type)
    
    def can_alert(self, alert_type: str) -> bool:
        now = time.time()
        if alert_type in self.last_alert_time:
            if now - self.last_alert_time[alert_type] < self.alert_cooldown:
                return False
        self.last_alert_time[alert_type] = now
        return True
    
    def send_windows_notification(self, title: str, message: str):
        title_escaped = title.replace("'", "''").replace('"', '\\"')
        message_escaped = message.replace("'", "''").replace('"', '\\"')
        
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $APP_ID = 'TradingBot'
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title_escaped}</text>
                    <text id="2">{message_escaped}</text>
                </binding>
            </visual>
        </toast>
        "@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
        '''
        
        try:
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"[УВЕДОМЛЕНИЕ] {title}")
            return True
        except Exception as e:
            print(f"[WARNING] Ошибка уведомления PowerShell: {e}")
            return False
    
    def alert_signal(self, signal_info: dict):
        signal_code = signal_info['signal']
        signal_desc = signal_info['signal_description']
        
        if signal_code == 2:
            alert_type = "STRONG_BUY"
            title = "🟢 STRONG BUY СИГНАЛ!"
            emoji = "🔥"
        elif signal_code == -2:
            alert_type = "STRONG_SELL"
            title = "🔴 STRONG SELL СИГНАЛ!"
            emoji = "💀"
        elif signal_code == 1:
            alert_type = "BUY"
            title = "🟡 BUY СИГНАЛ"
            emoji = "📈"
        elif signal_code == -1:
            alert_type = "SELL"
            title = "🟠 SELL СИГНАЛ"
            emoji = "📉"
        else:
            return
        
        if signal_code in [2, -2]:
            if not self.can_alert(alert_type):
                print(f"[ИНФО] Сигнал {alert_type} пропущен (кулдаун {self.alert_cooldown}с)")
                return
        
        # Вывод в консоль
        print(f"\n{'='*60}")
        print(f"  {emoji} {signal_desc}")
        print(f"{'='*60}")
        print(f"  💰 Цена закрытия: ${signal_info['close']:.4f}")
        print(f"  📊 EMA 5: ${signal_info['EMA_5']:.4f}")
        print(f"  📊 EMA 20: ${signal_info['EMA_20']:.4f}")
        print(f"  🎯 Parabolic SAR: ${signal_info['PSAR']:.4f}")
        print(f"  🔄 Направление PSAR: {signal_info['PSAR_direction']}")
        
        if 'rsi' in signal_info:
            rsi_val = signal_info['rsi']
            rsi_status = "Перекуплен" if rsi_val > 70 else "Перепродан" if rsi_val < 30 else "Нейтрально"
            print(f"  📈 RSI 5: {rsi_val:.1f} ({rsi_status})")
        
        if 'macd_hist' in signal_info:
            macd_val = signal_info['macd_hist']
            macd_status = "Бычий" if macd_val > 0 else "Медвежий"
            print(f"  📉 MACD Hist: {macd_val:.4f} ({macd_status})")
        
        if 'adx' in signal_info:
            adx_val = signal_info['adx']
            adx_status = "Сильный тренд" if adx_val > 25 else "Слабый тренд" if adx_val > 20 else "Боковик"
            print(f"  💪 ADX: {adx_val:.1f} ({adx_status})")
        
        print(f"  🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Звук
        self.play_sound(signal_code)
        
        # Уведомление
        message = f"{signal_desc}\n"
        message += f"Цена: ${signal_info['close']:.4f}\n"
        message += f"EMA 5: ${signal_info['EMA_5']:.4f} | EMA 20: ${signal_info['EMA_20']:.4f}\n"
        message += f"PSAR: ${signal_info['PSAR']:.4f} ({signal_info['PSAR_direction']})"
        if 'rsi' in signal_info:
            message += f"\nRSI: {signal_info['rsi']:.1f} | ADX: {signal_info['adx']:.1f}"
        message += f"\nВремя: {datetime.now().strftime('%H:%M:%S')}"
        
        self.send_windows_notification(title, message)
        self._log_signal(signal_info)
    
    def _log_signal(self, signal_info: dict):
        log_file = "signals_log.txt"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"\n{'='*60}\n"
        log_entry += f"[{timestamp}] {signal_info['signal_description']}\n"
        log_entry += f"{'='*60}\n"
        log_entry += f"  Цена: ${signal_info['close']:.4f}\n"
        log_entry += f"  EMA 5: ${signal_info['EMA_5']:.4f}\n"
        log_entry += f"  EMA 20: ${signal_info['EMA_20']:.4f}\n"
        log_entry += f"  PSAR: ${signal_info['PSAR']:.4f}\n"
        log_entry += f"  Направление PSAR: {signal_info['PSAR_direction']}\n"
        
        if 'rsi' in signal_info:
            log_entry += f"  RSI 5: {signal_info['rsi']:.1f}\n"
        if 'macd_hist' in signal_info:
            log_entry += f"  MACD Hist: {signal_info['macd_hist']:.4f}\n"
        if 'adx' in signal_info:
            log_entry += f"  ADX: {signal_info['adx']:.1f}\n"
        
        log_entry += "-" * 60 + "\n"
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[WARNING] Ошибка записи лога: {e}")


# ============================================================================
# ОРИГИНАЛЬНАЯ СТРАТЕГИЯ
class OriginalTradingStrategy:
    """
    ОРИГИНАЛЬНАЯ СТРАТЕГИЯ:
    - EMA 5
    - EMA 20
    - Parabolic SAR (acceleration=0.01, max_acceleration=0.3)
    - Сигналы на пересечении EMA + подтверждение PSAR
    + Дополнительные турбо стратегии для усиления сигналов
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.signals_df = None
        self.ema_short_period = 5
        self.ema_long_period = 20
        self.sar_acceleration = 0.01
        self.sar_max_acceleration = 0.3
        
    def calculate_ema(self, period: int, column: str = 'close') -> pd.Series:
        return self.df[column].ewm(span=period, adjust=False).mean()
    
    def calculate_parabolic_sar(self) -> Tuple[pd.Series, pd.Series]:
        high = self.df['high'].values
        low = self.df['low'].values
        close = self.df['close'].values
        n = len(self.df)
        
        psar = np.zeros(n)
        psar_direction = np.zeros(n)
        acceleration_factor = self.sar_acceleration
        max_acceleration = self.sar_max_acceleration
        
        if close[1] > close[0]:
            trend_direction = 1
            psar[0] = low[0]
            extreme_point = high[0]
        else:
            trend_direction = -1
            psar[0] = high[0]
            extreme_point = low[0]
        
        psar[1] = psar[0] + acceleration_factor * (extreme_point - psar[0])
        psar_direction[0] = trend_direction
        psar_direction[1] = trend_direction
        
        for i in range(2, n):
            if trend_direction == 1:
                if low[i] < psar[i-1]:
                    trend_direction = -1
                    psar[i] = extreme_point
                    extreme_point = low[i]
                    acceleration_factor = self.sar_acceleration
                else:
                    if high[i] > extreme_point:
                        extreme_point = high[i]
                        acceleration_factor = min(acceleration_factor + self.sar_acceleration, max_acceleration)
                    psar[i] = psar[i-1] + acceleration_factor * (extreme_point - psar[i-1])
                    if i >= 2:
                        psar[i] = min(psar[i], low[i-1], low[i-2])
            else:
                if high[i] > psar[i-1]:
                    trend_direction = 1
                    psar[i] = extreme_point
                    extreme_point = high[i]
                    acceleration_factor = self.sar_acceleration
                else:
                    if low[i] < extreme_point:
                        extreme_point = low[i]
                        acceleration_factor = min(acceleration_factor + self.sar_acceleration, max_acceleration)
                    psar[i] = psar[i-1] + acceleration_factor * (extreme_point - psar[i-1])
                    if i >= 2:
                        psar[i] = max(psar[i], high[i-1], high[i-2])
            
            psar_direction[i] = trend_direction
        
        return pd.Series(psar, index=self.df.index), pd.Series(psar_direction, index=self.df.index)
    
    def calculate_rsi(self, period: int = 5) -> pd.Series:
        delta = self.df['close'].diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        rs = gain / loss
        return 100.0 - (100.0 / (1.0 + rs))
    
    def calculate_macd(self, fast: int = 6, slow: int = 13, signal: int = 5):
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger(self, period: int = 12, std: float = 2.0):
        sma = self.df['close'].rolling(window=period).mean()
        std_dev = self.df['close'].rolling(window=period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        bb_width = (upper - lower) / sma * 100.0
        return upper, sma, lower, bb_width
    
    def calculate_adx(self, period: int = 7):
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        
        plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
        minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
        
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100.0
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
        
        return adx, plus_di, minus_di
    
    def _signal_macd_turbo(self, df: pd.DataFrame) -> pd.Series:
        _, _, hist = self.calculate_macd()
        buy = (hist > hist.shift(1)) & (hist.shift(1) > hist.shift(2)) & (hist.shift(2) < 0)
        sell = (hist < hist.shift(1)) & (hist.shift(1) < hist.shift(2)) & (hist.shift(2) > 0)
        signal = pd.Series(0, index=df.index)
        signal[buy] = 1
        signal[sell] = -1
        return signal
    
    def _signal_ema_rsi_turbo(self, df: pd.DataFrame) -> pd.Series:
        ema5 = self.calculate_ema(5)
        ema10 = self.calculate_ema(10)
        rsi5 = self.calculate_rsi(5)
        buy = (ema5 > ema10) & (rsi5 > 50) & (rsi5 < 70) & (ema5.shift(1) <= ema10.shift(1))
        sell = (ema5 < ema10) & (rsi5 < 50) & (rsi5 > 30) & (ema5.shift(1) >= ema10.shift(1))
        signal = pd.Series(0, index=df.index)
        signal[buy] = 1
        signal[sell] = -1
        return signal
    
    def _signal_sar_adx(self, df: pd.DataFrame) -> pd.Series:
        psar, psar_dir = self.calculate_parabolic_sar()
        adx, plus_di, minus_di = self.calculate_adx(7)
        buy = (psar < df['close']) & (adx > 20) & (plus_di > minus_di) & (psar_dir == 1) & (psar_dir.shift(1) == -1)
        sell = (psar > df['close']) & (adx > 20) & (minus_di > plus_di) & (psar_dir == -1) & (psar_dir.shift(1) == 1)
        signal = pd.Series(0, index=df.index)
        signal[buy] = 1
        signal[sell] = -1
        return signal
    
    def generate_signals(self) -> pd.DataFrame:
        df = self.df.copy()
        
        # Основная стратегия EMA + PSAR
        df['EMA_5'] = self.calculate_ema(self.ema_short_period)
        df['EMA_20'] = self.calculate_ema(self.ema_long_period)
        df['PSAR'], df['PSAR_direction'] = self.calculate_parabolic_sar()
        
        df['EMA_cross'] = 0
        df.loc[df['EMA_5'] > df['EMA_20'], 'EMA_cross'] = 1
        df.loc[df['EMA_5'] < df['EMA_20'], 'EMA_cross'] = -1
        
        df['EMA_signal'] = 0
        df.loc[(df['EMA_cross'] == 1) & (df['EMA_cross'].shift(1) == -1), 'EMA_signal'] = 1
        df.loc[(df['EMA_cross'] == -1) & (df['EMA_cross'].shift(1) == 1), 'EMA_signal'] = -1
        
        df['Price_vs_PSAR'] = np.where(df['close'] > df['PSAR'], 1, -1)
        
        df['Base_Signal'] = 0
        buy_cond = (df['EMA_signal'] == 1) & (df['close'] > df['PSAR'])
        sell_cond = (df['EMA_signal'] == -1) & (df['close'] < df['PSAR'])
        df.loc[buy_cond, 'Base_Signal'] = 1
        df.loc[sell_cond, 'Base_Signal'] = -1
        
        psar_buy = (df['PSAR_direction'] == 1) & (df['PSAR_direction'].shift(1) == -1)
        psar_sell = (df['PSAR_direction'] == -1) & (df['PSAR_direction'].shift(1) == 1)
        
        turbo_macd = self._signal_macd_turbo(df)
        turbo_ema_rsi = self._signal_ema_rsi_turbo(df)
        turbo_sar_adx = self._signal_sar_adx(df)
        
        df['Signal'] = 0
        
        strong_buy = (
            (df['Base_Signal'] == 1) & 
            psar_buy & 
            ((turbo_macd == 1).astype(int) + (turbo_ema_rsi == 1).astype(int) + (turbo_sar_adx == 1).astype(int) >= 2)
        )
        
        strong_sell = (
            (df['Base_Signal'] == -1) & 
            psar_sell & 
            ((turbo_macd == -1).astype(int) + (turbo_ema_rsi == -1).astype(int) + (turbo_sar_adx == -1).astype(int) >= 2)
        )
        
        normal_buy = (
            (df['Base_Signal'] == 1) & 
            ((turbo_macd == 1).astype(int) + (turbo_ema_rsi == 1).astype(int) + (turbo_sar_adx == 1).astype(int) >= 1)
        )
        
        normal_sell = (
            (df['Base_Signal'] == -1) & 
            ((turbo_macd == -1).astype(int) + (turbo_ema_rsi == -1).astype(int) + (turbo_sar_adx == -1).astype(int) >= 1)
        )
        
        df.loc[strong_buy, 'Signal'] = 2
        df.loc[strong_sell, 'Signal'] = -2
        df.loc[normal_buy & ~strong_buy, 'Signal'] = 1
        df.loc[normal_sell & ~strong_sell, 'Signal'] = -1
        
        df['RSI_5'] = self.calculate_rsi(5)
        macd_line, signal_line, hist = self.calculate_macd()
        df['MACD_hist'] = hist
        df['MACD_line'] = macd_line
        df['MACD_signal'] = signal_line
        df['BB_upper'], df['BB_mid'], df['BB_lower'], df['BB_width'] = self.calculate_bollinger()
        df['ADX'], df['plus_DI'], df['minus_DI'] = self.calculate_adx(7)
        
        self.signals_df = df
        return df
    
    def get_latest_signal(self) -> dict:
        if self.signals_df is None:
            self.generate_signals()
        
        latest = self.signals_df.iloc[-1]
        
        signal_code = int(latest['Signal'])
        if signal_code == 2:
            desc = '🔥 STRONG BUY (EMA крест + PSAR + 3 стратегии)'
        elif signal_code == 1:
            desc = '📈 BUY (EMA крест + PSAR + 1 стратегия)'
        elif signal_code == -1:
            desc = '📉 SELL (EMA крест + PSAR + 1 стратегия)'
        elif signal_code == -2:
            desc = '💀 STRONG SELL (EMA крест + PSAR + 3 стратегии)'
        else:
            desc = '⏸️ HOLD (нет сигнала)'
        
        return {
            'timestamp': latest['timestamp'],
            'close': latest['close'],
            'EMA_5': latest['EMA_5'],
            'EMA_20': latest['EMA_20'],
            'PSAR': latest['PSAR'],
            'PSAR_direction': 'UP' if latest['PSAR_direction'] == 1 else 'DOWN',
            'signal': signal_code,
            'signal_description': desc,
            'rsi': latest.get('RSI_5', 0),
            'macd_hist': latest.get('MACD_hist', 0),
            'adx': latest.get('ADX', 0)
        }
    
    def get_all_signals(self) -> pd.DataFrame:
        """Получить все сигналы из датафрейма"""
        if self.signals_df is None:
            self.generate_signals()
        
        # Возвращаем только строки с сигналами
        signals = self.signals_df[self.signals_df['Signal'] != 0].copy()
        return signals[['timestamp', 'close', 'Signal', 'EMA_5', 'EMA_20', 'PSAR', 'PSAR_direction', 
                       'RSI_5', 'MACD_hist', 'ADX']]
    
    def print_indicators_table(self):
        if self.signals_df is None:
            self.generate_signals()
        
        latest = self.signals_df.iloc[-1]
        prev = self.signals_df.iloc[-2] if len(self.signals_df) > 1 else latest
        
        print("\n" + "=" * 60)
        print("  📊 ТЕКУЩИЕ ЗНАЧЕНИЯ ИНДИКАТОРОВ")
        print("=" * 60)
        
        ema5_diff = latest['EMA_5'] - prev['EMA_5']
        ema20_diff = latest['EMA_20'] - prev['EMA_20']
        print(f"  EMA 5:      ${latest['EMA_5']:.4f}  ({'+' if ema5_diff >= 0 else ''}{ema5_diff:.4f})")
        print(f"  EMA 20:     ${latest['EMA_20']:.4f}  ({'+' if ema20_diff >= 0 else ''}{ema20_diff:.4f})")
        print(f"  Статус EMA: {'🟢 Бычий (EMA5 > EMA20)' if latest['EMA_5'] > latest['EMA_20'] else '🔴 Медвежий (EMA5 < EMA20)'}")
        
        psar_pos = "ВЫШЕ цены" if latest['PSAR'] > latest['close'] else "НИЖЕ цены"
        psar_dir = latest['PSAR_direction']
        print(f"  PSAR:       ${latest['PSAR']:.4f}  ({psar_pos}, тренд: {psar_dir})")
        
        if 'RSI_5' in latest:
            rsi = latest['RSI_5']
            if rsi > 70:
                rsi_status = "🔴 Перекуплен"
            elif rsi < 30:
                rsi_status = "🟢 Перепродан"
            else:
                rsi_status = "⚪ Нейтрально"
            print(f"  RSI 5:      {rsi:.1f}  ({rsi_status})")
        
        if 'MACD_hist' in latest:
            macd = latest['MACD_hist']
            macd_status = "🟢 Растёт" if macd > 0 else "🔴 Падает"
            print(f"  MACD Hist:  {macd:.4f}  ({macd_status})")
        
        if 'ADX' in latest:
            adx = latest['ADX']
            if adx > 25:
                adx_status = "🟢 Сильный тренд"
            elif adx > 20:
                adx_status = "🟡 Умеренный тренд"
            else:
                adx_status = "⚪ Боковик"
            print(f"  ADX 7:      {adx:.1f}  ({adx_status})")
        
        if 'BB_width' in latest:
            bb_w = latest['BB_width']
            print(f"  BB Width:   {bb_w:.2f}%")
        
        signal_code = int(latest['Signal'])
        signal_map = {2: '🟢 STRONG BUY', 1: '🟡 BUY', 0: '⚪ HOLD', -1: '🟠 SELL', -2: '🔴 STRONG SELL'}
        print(f"\n  ТЕКУЩИЙ СИГНАЛ: {signal_map.get(signal_code, 'N/A')}")
        print("=" * 60 + "\n")


# ============================================================================
# ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ И ОБРАБОТКИ ДАТАФРЕЙМА
def analyze_dataframe(df: pd.DataFrame, 
                      enable_sound: bool = True, 
                      enable_notifications: bool = True,
                      show_table: bool = True,
                      show_all_signals: bool = False) -> dict:
    """
    Загрузка датафрейма и анализ сигналов.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм с колонками:
        - timestamp (datetime)
        - open (float)
        - high (float)
        - low (float)
        - close (float)
        - volume (int, опционально)
    
    enable_sound : bool
        Включить звуковые сигналы
    
    enable_notifications : bool
        Включить уведомления Windows
    
    show_table : bool
        Показать таблицу индикаторов
    
    show_all_signals : bool
        Показать все найденные сигналы в датафрейме
    
    Returns:
    --------
    dict с информацией о последнем сигнале
    """
    
    # Проверка обязательных колонок
    required_columns = ['timestamp', 'open', 'high', 'low', 'close']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"В датафрейме отсутствуют обязательные колонки: {missing_columns}")
    
    # Создаем стратегию
    strategy = OriginalTradingStrategy(df)
    
    # Генерируем сигналы
    signals_df = strategy.generate_signals()
    
    # Получаем последний сигнал
    latest_signal = strategy.get_latest_signal()
    
    # Показываем таблицу индикаторов
    if show_table:
        strategy.print_indicators_table()
    
    # Показываем все сигналы
    if show_all_signals:
        all_signals = strategy.get_all_signals()
        if len(all_signals) > 0:
            print("\n" + "=" * 60)
            print("  📋 ВСЕ НАЙДЕННЫЕ СИГНАЛЫ")
            print("=" * 60)
            
            for idx, row in all_signals.iterrows():
                sig_code = int(row['Signal'])
                sig_map = {2: '🟢 STRONG BUY', 1: '🟡 BUY', -1: '🟠 SELL', -2: '🔴 STRONG SELL'}
                sig_name = sig_map.get(sig_code, 'N/A')
                
                print(f"  {row['timestamp']} | {sig_name} | Цена: ${row['close']:.2f} | "
                      f"EMA5: ${row['EMA_5']:.2f} | EMA20: ${row['EMA_20']:.2f} | "
                      f"PSAR: ${row['PSAR']:.2f} | RSI: {row['RSI_5']:.1f} | ADX: {row['ADX']:.1f}")
            
            print(f"\n  Всего сигналов: {len(all_signals)}")
            print("=" * 60 + "\n")
        else:
            print("\n  ℹ️ Сигналов не найдено в данном датафрейме\n")
    
    # Отправляем уведомление если есть сигнал
    if latest_signal['signal'] != 0 and (enable_sound or enable_notifications):
        alert = AlertSystem()
        
        # Вывод в консоль
        signal_code = latest_signal['signal']
        signal_desc = latest_signal['signal_description']
        
        if signal_code == 2:
            emoji = "🔥"
        elif signal_code == -2:
            emoji = "💀"
        elif signal_code == 1:
            emoji = "📈"
        elif signal_code == -1:
            emoji = "📉"
        else:
            emoji = "📊"
        
        print(f"\n{'='*60}")
        print(f"  {emoji} ПОСЛЕДНИЙ СИГНАЛ: {signal_desc}")
        print(f"{'='*60}")
        print(f"  💰 Цена: ${latest_signal['close']:.4f}")
        print(f"  📊 EMA 5: ${latest_signal['EMA_5']:.4f}")
        print(f"  📊 EMA 20: ${latest_signal['EMA_20']:.4f}")
        print(f"  🎯 PSAR: ${latest_signal['PSAR']:.4f} ({latest_signal['PSAR_direction']})")
        
        if 'rsi' in latest_signal:
            print(f"  📈 RSI 5: {latest_signal['rsi']:.1f}")
        if 'macd_hist' in latest_signal:
            print(f"  📉 MACD Hist: {latest_signal['macd_hist']:.4f}")
        if 'adx' in latest_signal:
            print(f"  💪 ADX: {latest_signal['adx']:.1f}")
        
        print(f"  🕐 Время сигнала: {latest_signal['timestamp']}")
        print(f"{'='*60}\n")
        
        # Звук и уведомление
        if enable_sound:
            alert.play_sound(signal_code)
        
        if enable_notifications and signal_code in [2, -2]:
            alert.alert_signal(latest_signal)
    
    return latest_signal