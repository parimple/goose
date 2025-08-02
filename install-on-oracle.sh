#!/bin/bash
# Install script for Goose on Oracle server

set -e

echo "=== Installing Rust and Goose on Oracle ==="

# Install Rust
echo "1. Installing Rust..."
if ! command -v rustc &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "Rust already installed"
fi

# Verify Rust installation
rustc --version
cargo --version

# Install build dependencies
echo "2. Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libssl-dev protobuf-compiler

# Clone UltraThink-Goose repository
echo "3. Cloning UltraThink-Goose repository..."
cd ~/Projects
if [ ! -d "ultrathink-goose" ]; then
    git clone https://github.com/patrykpyzel/ultrathink-goose.git
    cd ultrathink-goose
else
    cd ultrathink-goose
    git pull origin main
fi

# Build Goose with UltraThink extensions
echo "4. Building Goose with UltraThink extensions..."
cargo build --release

# Install Goose binary
echo "5. Installing Goose binary..."
sudo cp target/release/goose /usr/local/bin/
sudo chmod +x /usr/local/bin/goose

# Verify installation
echo "6. Verifying installation..."
goose --version

echo "=== Goose installation complete! ==="