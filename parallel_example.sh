ls
echo $1
echo $2

# executor always
cd /tmp
ls

# first worker will pick this branch
# executor set-dependent
sleep 5
sleep 5
sleep 5
# example of a branch
# executor tag branch_origin
sleep 5
sleep 5
# executor tag branch_2
sleep 5

# worker 2 can't process this because it waits on worker 1's task
# executor set-independent
# executor set-dependent
# executor if branch_origin
sleep 5

# this one will have to wait and be picked up by worker 1
# executor if branch_2
sleep 5

# worker 2 will pick this branch
# reset dependencies below this line
# executor set-independent

# executor set-dependent
sleep 5
sleep 5
sleep 5
sleep 5

# after it is done, worker 2 can wait until a new branch opens:
# this happens at line 23 after worker 1 processes line 16
