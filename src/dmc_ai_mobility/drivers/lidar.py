import os
import ydlidar
import time
import sys

# 同じディレクトリにあるライブラリを読み込む設定
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("LiDAR SDK initializing...")
    ydlidar.os_init()
    
    port = "/dev/ttyAMA0"
    laser = ydlidar.CYdLidar()
    
    # --- T-mini Plus 推奨設定 ---
    laser.setlidaropt(ydlidar.LidarPropSerialPort, port)
    laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, 230400)
    laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
    laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
    laser.setlidaropt(ydlidar.LidarPropScanFrequency, 7.0) # 7.0Hz
    laser.setlidaropt(ydlidar.LidarPropSampleRate, 4)      # 4k sample rate
    laser.setlidaropt(ydlidar.LidarPropSingleChannel, True)
    laser.setlidaropt(ydlidar.LidarPropIntenstiy, True)
    laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
    laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)
    laser.setlidaropt(ydlidar.LidarPropMaxRange, 16.0)
    laser.setlidaropt(ydlidar.LidarPropMinRange, 0.1)

    # 接続と初期化
    ret = laser.initialize()
    if ret:
        ret = laser.turnOn()
        if ret:
            print("LiDAR Running! (Press Ctrl+C to stop)")
            scan = ydlidar.LaserScan()
            
            try:
                while ret and ydlidar.os_isOk():
                    r = laser.doProcessSimple(scan)
                    if r:
                        # データ取得成功
                        points = scan.points
                        count = points.size()
                        
                        # 正面方向 (0度付近) のデータを抽出
                        front_dists = []
                        for i in range(count):
                            p = points[i]
                            dist = p.range
                            # ラジアン→度変換
                            angle_deg = (p.angle * 180) / 3.14159265359
                            
                            # エラー値(0)を除外
                            if dist == 0: continue
                            
                            # 正面 ±5度 (355度〜360度, 0度〜5度)
                            if angle_deg >= 355 or angle_deg <= 5:
                                front_dists.append(dist)
                        
                        # 平均値を表示
                        if len(front_dists) > 0:
                            avg = sum(front_dists) / len(front_dists)
                            print(f"Front: {avg:.3f} m  (Samples: {len(front_dists)})")
                        else:
                            pass
                            
                    time.sleep(0.05)
                    
            except KeyboardInterrupt:
                print("\nStopping...")
            
            laser.turnOff()
            laser.disconnecting()
        else:
            print("Failed to turn on")
    else:
        print(f"Error: Could not connect to {port}")

if __name__ == "__main__":
    main()
