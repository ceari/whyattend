#!/usr/bin/env bash

export DEBIAN_FRONTEND=noninteractive

MYSQL_ROOT_PASSWORD='whyattend'

apt-get update

debconf-set-selections <<< "mysql-server-5.7 mysql-server/root_password password $MYSQL_ROOT_PASSWORD"
debconf-set-selections <<< "mysql-server-5.7 mysql-server/root_password_again password $MYSQL_ROOT_PASSWORD"

apt-get -y install mysql-server

sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf

service mysql restart

mysql -uroot -pwhyattend -e "grant all privileges on *.* to 'whyattend'@'%' identified by 'whyattend'; flush privileges;"
