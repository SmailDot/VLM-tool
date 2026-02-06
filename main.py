import sys
import os
import subprocess
import threading
import time
import atexit

# Global reference for cleanup
ngrok_tunnel = None


def start_ngrok_tunnel(port: int) -> str | None:
    """Start ngrok tunnel for Streamlit and return public URL"""
    global ngrok_tunnel
    try:
        from pyngrok import ngrok
        
        # Connect to ngrok
        ngrok_tunnel = ngrok.connect(str(port), bind_tls=True)
        public_url = ngrok_tunnel.public_url
        
        print("=" * 60)
        print("🌐 NGROK TUNNEL ACTIVE - REMOTE ACCESS ENABLED")
        print("=" * 60)
        print(f"📡 Public URL: {public_url}")
        print(f"📡 Share this URL to access from anywhere!")
        print("=" * 60)
        
        return public_url
        
    except ImportError:
        print("[Warning] pyngrok not installed. Run: pip install pyngrok")
        print("[Warning] Remote access disabled. Only localhost available.")
        return None
    except Exception as e:
        print(f"[Warning] ngrok failed: {e}")
        print("[Warning] Remote access disabled. Only localhost available.")
        return None


def cleanup_ngrok():
    """Cleanup ngrok tunnel on exit"""
    global ngrok_tunnel
    if ngrok_tunnel and ngrok_tunnel.public_url:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(ngrok_tunnel.public_url)
            print("\n[ngrok] Tunnel closed.")
        except:
            pass


def main():
    """
    NKUST AoV Tool Launcher
    
    This script serves as a simple entry point to launch the Streamlit application.
    Optionally starts ngrok tunnel for remote access.
    """
    
    # Get the absolute path of the current script directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Configuration
    streamlit_port = int(os.environ.get('STREAMLIT_PORT', 8501))
    use_ngrok = os.environ.get('USE_NGROK', 'true').lower() == 'true'

    print("===================================================")
    print("       NKUST AoV Tool - Python Launcher")
    print("===================================================")
    print(f"🚀 Launching application...")
    print(f"📂 Working Directory: {base_dir}")
    print(f"🐍 Python Executable: {sys.executable}")
    print(f"🔌 Streamlit Port: {streamlit_port}")
    print("---------------------------------------------------")
    
    # Register cleanup
    atexit.register(cleanup_ngrok)
    
    # Start ngrok if enabled
    if use_ngrok:
        # Start ngrok in background (slight delay to let streamlit start first)
        def delayed_ngrok():
            time.sleep(3)  # Wait for Streamlit to start
            start_ngrok_tunnel(streamlit_port)
        
        ngrok_thread = threading.Thread(target=delayed_ngrok, daemon=True)
        ngrok_thread.start()
    else:
        print("[Info] ngrok disabled. Set USE_NGROK=true to enable remote access.")
    
    print("---------------------------------------------------")
    print("Press Ctrl+C to stop the server.")
    print("---------------------------------------------------")

    # Command to run streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", "aov_app.py",
        "--server.port", str(streamlit_port),
        "--server.address", "0.0.0.0",  # Allow external connections
        "--server.headless", "true"     # No auto-open browser on server
    ]

    try:
        subprocess.run(cmd, cwd=base_dir, check=True)
        
    except KeyboardInterrupt:
        print("\n\n👋 Application stopped by user.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Application crashed with exit code: {e.returncode}")
        print("Tip: Check the error messages above for details.")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
