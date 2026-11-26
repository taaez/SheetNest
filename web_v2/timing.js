// 계산 전 예상 시간을 위한 자료. tools 없이 손으로 고치지 말 것: 측정값이 바뀌면 다시 만든다.
// table: 준비된 도면의 방법별 계산 시간(초). 실험 3(tools/exp3_instances.py)의 측정값이다. null은 10분 안에 끝나지 않음.
//        2026-11-26, main ffc1643, PC의 CPython 3.13, rows 기본값 200, 10초 미만은 5회 평균, 두 개씩 동시에 측정.
// factor: 브라우저(Pyodide)가 PC보다 느린 배수. 0.5초 넘는 계산 6건에서 1.5~1.9배였다.
// model: 직접 올린 도면용. log(초) = a + n·log(조각 수) + s·log(종류별 볼록 조각 수의 합) + t·log(종류 수).
//        sOver: 볼록 조각 수의 합이 이 값 이상이면 10분 초과로 본다(실험 3에서 그런 인스턴스는 모두 시간 초과였다).
//        실험 3에서 끝난 실행과 복제 입력(수량 2~16배)으로 맞췄다. 하나씩 빼고 맞혀 보면 삼각법과 NFP는 대부분 실제의 2배 안쪽이다.
export const TIMING = {
 "factor": 1.7,
 "capSeconds": 600,
 "table": {
  "albano": {
   "raster": 0.0386,
   "trig": 0.8505,
   "nfp": 0.071
  },
  "blaz1": {
   "raster": 0.0383,
   "trig": 0.4272,
   "nfp": 0.0358
  },
  "dagli": {
   "raster": 0.0296,
   "trig": 0.3951,
   "nfp": 0.0372
  },
  "fu": {
   "raster": 0.0179,
   "trig": 0.0823,
   "nfp": 0.0032
  },
  "gardeyn0": {
   "raster": 0.0522,
   "trig": 153.67,
   "nfp": null
  },
  "gardeyn1": {
   "raster": 0.0268,
   "trig": 53.25,
   "nfp": null
  },
  "gardeyn2": {
   "raster": 0.6348,
   "trig": null,
   "nfp": null
  },
  "gardeyn3": {
   "raster": 0.7483,
   "trig": null,
   "nfp": null
  },
  "gardeyn4": {
   "raster": 0.1009,
   "trig": null,
   "nfp": null
  },
  "gardeyn5": {
   "raster": 0.1029,
   "trig": null,
   "nfp": null
  },
  "gardeyn6": {
   "raster": 1.1,
   "trig": null,
   "nfp": null
  },
  "gardeyn7": {
   "raster": 0.2045,
   "trig": 214.17,
   "nfp": null
  },
  "gardeyn8": {
   "raster": 0.7843,
   "trig": null,
   "nfp": null
  },
  "gardeyn9": {
   "raster": 0.1743,
   "trig": null,
   "nfp": null
  },
  "jakobs1": {
   "raster": 0.0116,
   "trig": 0.4244,
   "nfp": 0.1369
  },
  "jakobs2": {
   "raster": 0.0173,
   "trig": 0.4928,
   "nfp": 0.1014
  },
  "mao": {
   "raster": 0.0111,
   "trig": 0.638,
   "nfp": 0.0856
  },
  "marques": {
   "raster": 0.0172,
   "trig": 0.3677,
   "nfp": 0.0603
  },
  "shapes0": {
   "raster": 0.0208,
   "trig": 0.7122,
   "nfp": 0.1284
  },
  "shapes1": {
   "raster": 0.0221,
   "trig": 0.6866,
   "nfp": 0.1337
  },
  "shirts": {
   "raster": 0.0366,
   "trig": 1.47,
   "nfp": 0.2113
  },
  "swim": {
   "raster": 0.024,
   "trig": 6.49,
   "nfp": 5.24
  },
  "trousers": {
   "raster": 0.0966,
   "trig": 1.82,
   "nfp": 0.1002
  }
 },
 "model": {
  "raster": {
   "a": -8.2203,
   "n": 0.9384,
   "s": 0.102,
   "t": 0.5294
  },
  "trig": {
   "a": -6.9094,
   "n": 1.0868,
   "s": 1.4254,
   "t": -0.707,
   "sOver": 570
  },
  "nfp": {
   "a": -10.9456,
   "n": 1.5239,
   "s": 2.1203,
   "t": -1.4668,
   "sOver": 253
  }
 }
};
