#!/bin/bash

read -p 'Choose to install online/offline (online/offline) ' install_method
read -p 'Choose to install type (install/reinstall/remove) ' install_type

echo "=============="
echo all
ls | grep '^[0-9]'
echo "=============="

read -p 'Choose the package folder to install (all/1_default/[package_folder_name]) ' package_name
FOLDERS=$(ls | grep '^[0-9]')

# 유효한 입력인지 확인
if [[ $install_method != 'online' && $install_method != 'offline' ]]; then
    echo 'Please enter it correctly (online/offline).'
    exit 1
fi

if [[ $install_type != 'install' && $install_type != 'reinstall' && $install_type != 'remove' ]]; then
    echo 'Please enter it correctly (install/reinstall/remove).'
    exit 1
fi

if [[ $package_name != 'all' && -z $package_name ]]; then
    echo 'Please enter it correctly (all/1_default/[package_folder_name]).'
    exit 1
fi

function run_all_installer() {
    for dir in $FOLDERS; do
        if [ -d "${dir}" ] && [ -f "${dir}/installer.sh" ]; then
            cd "${dir}" && . ./installer.sh $1 $2
            cd ..
        fi
    done
}

function run_specific_installer() {
    for dir in $FOLDERS; do
        if [[ $package_name == $dir ]]; then
            cd "${dir}" && . ./installer.sh $1 $2
            cd ..
        fi
    done
}

# Install/Remove Packages
if [[ $install_method == 'online' ]]; then
    if [[ $install_type == 'install' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer online install
        else 
            run_specific_installer online install
        fi

    elif [[ $install_type == 'reinstall' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer online remove
            run_all_installer online install
        else 
            run_specific_installer online remove
            run_specific_installer online install
        fi
    elif [[ $install_type == 'remove' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer online remove
        else 
            run_specific_installer online remove
        fi
    fi
else
    if [[ $install_type == 'install' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer offline install
        else 
            run_specific_installer offline install
        fi

    elif [[ $install_type == 'reinstall' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer offline remove
            run_all_installer offline install
        else 
            run_specific_installer offline remove
            run_specific_installer offline install
        fi
    elif [[ $install_type == 'remove' ]]; then
        if [[ $package_name == 'all' ]]; then
            run_all_installer offline remove
        else 
            run_specific_installer offline remove
        fi
    fi
fi

