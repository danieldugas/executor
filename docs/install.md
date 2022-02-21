# Install
```
pip3 install exectr
```

# Run
```
executor example.sh
```

# Caveats
Executor is meant for simple bash scripts, with many operations and only simple dependence.
For example, if I am converting a bunch of independent files I use it to keep track of which files have been converted,
which have failed, and easily parallelize the process.

Currently multiline if statements / for loops are not supported. For example:

```
if [[ $1 == "ok" ]]; then echo "yes"; fi
```

is supported,
but

```
if [[ $1 == "ok" ]]; then
  echo "yes"
fi
```

is not.
