# Install
```
pip3 install exectr
```

# Run
```
executor example.sh
```

# Parallelizing

Just run several times with the flag `--parallel`

like so (video):

[![parallel execution video](https://img.youtube.com/vi/fxsNkJKTa_w/0.jpg)](https://www.youtube.com/watch?v=fxsNkJKTa_w)

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
