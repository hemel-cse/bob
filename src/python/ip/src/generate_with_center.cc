/**
 * @author Laurent El Shafey <Laurent.El-Shafey@idiap.ch>
 * @author Andre Anjos <andre.anjos@idiap.ch>
 * @date Sun 20 Nov 18:18:16 2011 CET
 *
 * @brief Binds the generateWithCenter operation into python 
 */

#include "core/python/ndarray.h"
#include "ip/generateWithCenter.h"

using namespace boost::python;
namespace tp = Torch::python;
namespace ip = Torch::ip;
namespace ca = Torch::core::array;

template <typename T, int N>
static void inner_gwc (tp::const_ndarray src, tp::ndarray dst, int y, int x) {
  blitz::Array<T,N> dst_ = dst.bz<T,N>();
  ip::generateWithCenter<T>(src.bz<T,N>(), dst_, y, x);
}

static void gwc (tp::const_ndarray src, tp::ndarray dst, int y, int x) {
  const ca::typeinfo& info = src.type();

  if (info.nd != 2)
    PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());

  switch (info.dtype) {
    case ca::t_uint8: 
      return inner_gwc<uint8_t,2>(src, dst, y, x);
    case ca::t_uint16:
      return inner_gwc<uint16_t,2>(src, dst, y, x);
    case ca::t_float64:
      return inner_gwc<double,2>(src, dst, y, x);
    default:
      PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());
  }
}

template <typename T, int N>
static void inner_gwc2 (tp::const_ndarray src, tp::const_ndarray smask, 
    tp::ndarray dst, tp::ndarray dmask, int y, int x) {
  blitz::Array<T,N> dst_ = dst.bz<T,N>();
  blitz::Array<bool,N> dmask_ = dmask.bz<bool,N>();
  ip::generateWithCenter<T>(src.bz<T,N>(), smask.bz<bool,N>(), dst_, dmask_, y, x);
}

static void gwc2 (tp::const_ndarray src, tp::const_ndarray smask,
    tp::ndarray dst, tp::ndarray dmask, int y, int x) {

  const ca::typeinfo& info = src.type();

  if (info.nd != 2)
    PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());

  switch (info.dtype) {
    case ca::t_uint8: 
      return inner_gwc2<uint8_t,2>(src, smask, dst, dmask, y, x);
    case ca::t_uint16:
      return inner_gwc2<uint16_t,2>(src, smask, dst, dmask, y, x);
    case ca::t_float64:
      return inner_gwc2<double,2>(src, smask, dst, dmask, y, x);
    default:
      PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());
  }
}

template <typename T, int N>
static object inner_gwc_shape (tp::const_ndarray src, int y, int x) {
  return object(ip::getGenerateWithCenterShape<T>(src.bz<T,N>(), y, x));
}

static object gwc_shape (tp::const_ndarray src, int y, int x) {

  const ca::typeinfo& info = src.type();

  if (info.nd != 2)
    PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());

  switch (info.dtype) {
    case ca::t_uint8: 
      return inner_gwc_shape<uint8_t,2>(src, y, x);
    case ca::t_uint16:
      return inner_gwc_shape<uint16_t,2>(src, y, x);
    case ca::t_float64:
      return inner_gwc_shape<double,2>(src, y, x);
    default:
      PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());
  }
}

template <typename T, int N>
static object inner_gwc_offset (tp::const_ndarray src, int y, int x) {
  return object(ip::getGenerateWithCenterOffset<T>(src.bz<T,N>(), y, x));
}

static object gwc_offset (tp::const_ndarray src, int y, int x) {

  const ca::typeinfo& info = src.type();

  if (info.nd != 2)
    PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());

  switch (info.dtype) {
    case ca::t_uint8: 
      return inner_gwc_offset<uint8_t,2>(src, y, x);
    case ca::t_uint16:
      return inner_gwc_offset<uint16_t,2>(src, y, x);
    case ca::t_float64:
      return inner_gwc_offset<double,2>(src, y, x);
    default:
      PYTHON_ERROR(TypeError, "generate with center does not support type '%s'", info.str().c_str());
  }
}

void bind_ip_generate_with_center() {

  def("generateWithCenter", &gwc, (arg("src"), arg("dst"), arg("center_y"), arg("center_x")), "Extend a 2D blitz array/image, putting a given point in the center.");

  def("generateWithCenter", &gwc2, (arg("src"), arg("src_mask"), arg("dst"), arg("dst_mask"), arg("center_y"), arg("center_x")), "Extend a 2D blitz array/image, putting a given point in the center, taking mask into account.");

  def("getGenerateWithCenterShape", &gwc_shape, (arg("src"), arg("center_y"), arg("center_x")), "Return the shape of the output 2D blitz array/image, when calling generateWithCenter which puts a given point of an image in the center.");
  
  def("getGenerateWithCenterOffset", &gwc_offset, (arg("src"), arg("center_y"), arg("center_x")), "Return the offset of the output 2D blitz array/image, when calling generateWithCenter which puts a given point of an image in the center.");

}
