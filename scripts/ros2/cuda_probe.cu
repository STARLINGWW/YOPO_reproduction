#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>

#define CUDA_CHECK(call) do { cudaError_t error=(call); if(error!=cudaSuccess) { \
  std::fprintf(stderr,"CUDA error at line %d: %s\n",__LINE__,cudaGetErrorString(error)); return 1; } } while(0)

__global__ void fill(float* output) {
  const int index = threadIdx.x;
  output[index] = 2.0f * index + 1.0f;
}

int main() {
  cudaDeviceProp properties;
  CUDA_CHECK(cudaGetDeviceProperties(&properties, 0));
  float* device = nullptr;
  float output[256];
  CUDA_CHECK(cudaMalloc(&device, sizeof(output)));
  fill<<<1,256>>>(device);
  CUDA_CHECK(cudaGetLastError());
  CUDA_CHECK(cudaDeviceSynchronize());
  CUDA_CHECK(cudaMemcpy(output, device, sizeof(output), cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaFree(device));
  for(int i=0;i<256;++i) if(output[i] != 2.0f*i+1.0f) return 2;
  std::printf("{\"status\":\"passed\",\"scope\":\"native CUDA kernel in Ubuntu22.04 container\",\"device\":\"%s\",\"major\":%d,\"minor\":%d,\"values_checked\":256}\n",properties.name,properties.major,properties.minor);
}
