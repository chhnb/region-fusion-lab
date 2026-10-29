#include <stdlib.h>
#include <math.h>
void seed_image(float *j,int rows,int cols){srand(7);for(int k=0;k<rows*cols;k++){float v=rand()/(float)RAND_MAX;j[k]=(float)exp((double)v);}}
float q0_image(const float *j,int rows,int cols,int extent){float sum=0,sum2=0,tmp,mean,var;int nr=rows<extent?rows:extent,nc=cols<extent?cols:extent;for(int i=0;i<nr;i++)for(int k=0;k<nc;k++){tmp=j[i*cols+k];sum+=tmp;sum2+=tmp*tmp;}mean=sum/(nr*nc);var=sum2/(nr*nc)-mean*mean;return var/(mean*mean);}
