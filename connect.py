import mysql.connector

# These details are available on the first MySQL Workbench screen
# Usually called 'Local Instance'
dbuser = "root"  # PUT YOUR MySQL username here - usually root
dbpass = ""  # PUT YOUR PASSWORD HERE
dbhost = "localhost"
dbport = "3306"
dbname = "BookSense"

def getCursor():
    connection = mysql.connector.connect(
        user=dbuser,
        password=dbpass,
        host=dbhost,
        database=dbname,
        autocommit=True
    )
    dbconn = connection.cursor()
    return connection, dbconn
