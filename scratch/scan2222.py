import socket
import concurrent.futures

def scan_port(ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex((ip, 2222))
    sock.close()
    if result == 0:
        return ip
    return None

def main():
    print("Scanning subnet for port 2222...")
    ips = [f"192.168.68.{i}" for i in range(2, 105)]
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(scan_port, ips)
        for ip in results:
            if ip:
                found.append(ip)
    
    print(f"Devices with port 2222 open: {found}")

if __name__ == "__main__":
    main()
