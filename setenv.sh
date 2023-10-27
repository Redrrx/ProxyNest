#!/bin/bash

read -p "Enter your DB_URL: " DB_URL
read -p "Enter your DB_NAME: " DB_NAME
read -p "Enter your DB_USER: " DB_USER
read -s -p "Enter your DB_PASSWORD: " DB_PASSWORD

echo ""

echo "export DB_URL=$DB_URL" >> ~/.bashrc
echo "export DB_NAME=$DB_NAME" >> ~/.bashrc
echo "export DB_USER=$DB_USER" >> ~/.bashrc
echo "export DB_PASSWORD=$DB_PASSWORD" >> ~/.bashrc

echo "Environment variables have been set! You may need to restart your terminal session."
