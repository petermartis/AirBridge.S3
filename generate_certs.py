"""
Pre-build script for PlatformIO.
Generates embedded data .S files from certificates that ESP-IDF components need.
PlatformIO's SCons doesn't run ninja custom commands, so we do it here.
"""
import os
import subprocess
import sys

Import("env")

# Build dir
build_dir = env.subst("$BUILD_DIR")
cmake_bin = os.path.join(env.subst("$PROJECT_PACKAGES_DIR"), "tool-cmake", "bin", "cmake")
embed_script = os.path.join(
    env.subst("$PROJECT_PACKAGES_DIR"), "framework-espidf",
    "tools", "cmake", "scripts", "data_file_embed_asm.cmake"
)

# List of (source_cert, output_S, file_type)
project_dir = env.subst("$PROJECT_DIR")
managed = os.path.join(project_dir, "managed_components")

certs = [
    (os.path.join(managed, "espressif__esp_insights", "server_certs", "https_server.crt"),
     os.path.join(build_dir, "https_server.crt.S"), "TEXT"),
    (os.path.join(managed, "espressif__esp_rainmaker", "server_certs", "rmaker_mqtt_server.crt"),
     os.path.join(build_dir, "rmaker_mqtt_server.crt.S"), "TEXT"),
    (os.path.join(managed, "espressif__esp_rainmaker", "server_certs", "rmaker_claim_service_server.crt"),
     os.path.join(build_dir, "rmaker_claim_service_server.crt.S"), "TEXT"),
    (os.path.join(managed, "espressif__esp_rainmaker", "server_certs", "rmaker_ota_server.crt"),
     os.path.join(build_dir, "rmaker_ota_server.crt.S"), "TEXT"),
]

for data_file, source_file, file_type in certs:
    if os.path.exists(data_file) and not os.path.exists(source_file):
        print(f"Generating {os.path.basename(source_file)}...")
        subprocess.run([
            cmake_bin,
            "-D", f"DATA_FILE={data_file}",
            "-D", f"SOURCE_FILE={source_file}",
            "-D", f"FILE_TYPE={file_type}",
            "-P", embed_script,
        ], cwd=build_dir, check=True)
