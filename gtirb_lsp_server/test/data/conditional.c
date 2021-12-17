#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv){
  if(atoi(argv[1]) == 4){
    puts("Four!");
  } else {
    puts("Non-Four!");
  }
  return 0;
}
