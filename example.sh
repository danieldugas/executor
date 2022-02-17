ls

# executor always
cd /tmp
ls

# executor set-dependent
echo "bonjour monde"
echo "lorem ipsum"
touch /tmp/this
touch /tmp/that
touch ./there
touch \
  /tmp/other
cat /tmp/thiswillfail

# everything below this line will run even if previous commands fail
# executor set-independent

# executor tag made_any_case
touch /tmp/in_any_case

# executor if made_any_case
cat /tmp/in_any_case > ./those

# executor if 4
cat /tmp/this > ./these
