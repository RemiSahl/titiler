from typing import Dict, Optional, Union
import rasterio
from geojson_pydantic.features import Feature, FeatureCollection
from geojson_pydantic.geometries import Polygon
from rio_tiler.io import BaseReader
from rio_tiler.models import BandStatistics, Bounds, Info
from rio_tiler.utils import get_array_statistics
from morecantile import TileMatrixSet
from titiler.core.resources.enums import ImageType, MediaType
from titiler.core.utils import Timer

from starlette.requests import Request
from starlette.templating import Jinja2Templates

try:
    from importlib.resources import files as resources_files  # type: ignore
except ImportError:
    # Try backported to PY<39 `importlib_resources`.
    from importlib_resources import files as resources_files  # type: ignore


# TODO: mypy fails in python 3.9, we need to find a proper way to do this
templates = Jinja2Templates(directory=str(resources_files(__package__) / "templates"))  # type: ignore

def info_geojson(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, info_params: Dict={}) -> Feature:
    """Return dataset's basic info as a GeoJSON feature."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return Feature(
                geometry=Polygon.from_bounds(*src_dst.geographic_bounds),
                properties=src_dst.info(**info_params),
            )

def info_geojson_multi(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, asset_params: Dict) -> Feature:
    """Return dataset's basic info as a GeoJSON feature."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return Feature(
                geometry=Polygon.from_bounds(*src_dst.geographic_bounds),
                properties={
                    asset: asset_info
                    for asset, asset_info in src_dst.info(
                        **asset_params
                    ).items()
                },
            )

def info(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, info_params={}) -> Info:
    """Return dataset's basic info."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return src_dst.info(**info_params)

def assets(reader: BaseReader, env: Dict, src_path: str, reader_params) -> Info:
    """Return a list of supported assets."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return src_dst.assets

def bands(reader: BaseReader, env: Dict, src_path: str, reader_params) -> Info:
    """Return a list of supported bands."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return src_dst.bands

def bounds(reader: BaseReader, env: Dict, src_path: str, reader_params) -> Bounds:
    """Return the bounds of the COG."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return {"bounds": src_dst.geographic_bounds}

def statistics(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, stats_params, histogram_params, multi_assets: bool=False) -> Dict[str, BandStatistics]:
    """Get Dataset statistics."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            # Default to all available assets
            if multi_assets and not stats_params.assets and not stats_params.expression:
                stats_params.assets = src_dst.assets

            return src_dst.statistics(
                **stats_params,
                hist_options={**histogram_params},
            )

def geojson_statistics(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, geojson: Union[FeatureCollection, Feature], feature_params, stats_params, multi_assets: bool=False, multi_bands: bool=False):
    """Get Statistics from a geojson feature or featureCollection."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            # Default to all available assets
            if multi_assets and not feature_params.assets and not feature_params.expression:
                feature_params.assets = src_dst.assets

            # Default to all available bands
            if multi_bands and not feature_params.bands and not feature_params.expression:
                feature_params.bands = src_dst.bands

            # TODO: stream features for FeatureCollection
            if isinstance(geojson, FeatureCollection):
                for feature in geojson:
                    data = src_dst.feature(
                        feature.dict(exclude_none=True),
                        **feature_params,
                    )
                    stats = get_array_statistics(
                        data.as_masked(),
                        **stats_params,
                    )

                feature.properties = feature.properties or {}
                feature.properties.update(
                    {
                        # NOTE: because we use `src_dst.feature` the statistics will be in form of
                        # `Dict[str, BandStatistics]` and not `Dict[str, Dict[str, BandStatistics]]`
                        "statistics": {
                            f"{data.band_names[ix]}": BandStatistics(
                                **stats[ix]
                            )
                            for ix in range(len(stats))
                        }
                    }
                )

            else:  # simple feature
                data = src_dst.feature(
                    geojson.dict(exclude_none=True),
                    **feature_params,
                )
                stats = get_array_statistics(
                    data.as_masked(),
                    **stats_params,
                )

                geojson.properties = geojson.properties or {}
                geojson.properties.update(
                    {
                        "statistics": {
                            f"{data.band_names[ix]}": BandStatistics(
                                **stats[ix]
                            )
                            for ix in range(len(stats))
                        }
                    }
                )

            return geojson

def tile(
    reader: BaseReader,
    z: int,
    x: int,
    y: int,
    tms: TileMatrixSet,
    scale: int,
    format: ImageType,
    src_path,
    layer_params,
    dataset_params,
    postprocess_params,
    colormap,
    render_params,
    tile_buffer: Optional[float],
    reader_params,
    env: Dict,
):
    """Create map tile from a dataset."""
    timings = []

    tilesize = scale * 256

    with Timer() as t:
        with rasterio.Env(**env):
            with reader(src_path, tms=tms, **reader_params) as src_dst:
                data = src_dst.tile(
                    x,
                    y,
                    z,
                    tilesize=tilesize,
                    tile_buffer=tile_buffer,
                    **layer_params,
                    **dataset_params,
                )
                dst_colormap = getattr(src_dst, "colormap", None)
    timings.append(("dataread", round(t.elapsed * 1000, 2)))

    if not format:
        format = ImageType.jpeg if data.mask.all() else ImageType.png

    with Timer() as t:
        image = data.post_process(**postprocess_params)
    timings.append(("postprocess", round(t.elapsed * 1000, 2)))

    with Timer() as t:
        content = image.render(
            img_format=format.driver,
            colormap=colormap or dst_colormap,
            **format.profile,
            **render_params,
        )
    timings.append(("format", round(t.elapsed * 1000, 2)))

    return content, timings

def tilejson(
    reader: BaseReader, env: Dict, src_path: str, reader_params,
    tiles_url: str,
    minzoom: Optional[int],
    maxzoom: Optional[int],
) -> Dict:
    """Return TileJSON document for a dataset."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            return {
                "bounds": src_dst.geographic_bounds,
                "minzoom": minzoom if minzoom is not None else src_dst.minzoom,
                "maxzoom": maxzoom if maxzoom is not None else src_dst.maxzoom,
                "tiles": [tiles_url],
            }

def wmts(
    request: Request,
    reader: BaseReader,
    tile_format: ImageType,
    tms: TileMatrixSet,
    tiles_url: str,
    src_path,
    reader_params,
    env: Dict,
):
    """Returns a WMTS xml document."""
    with rasterio.Env(**env):
        with reader(src_path, tms=tms, **reader_params) as src_dst:
            bounds = src_dst.geographic_bounds
            minzoom = minzoom if minzoom is not None else src_dst.minzoom
            maxzoom = maxzoom if maxzoom is not None else src_dst.maxzoom

    tileMatrix = []
    for zoom in range(minzoom, maxzoom + 1):
        matrix = tms.matrix(zoom)
        tm = f"""
                <TileMatrix>
                    <ows:Identifier>{matrix.identifier}</ows:Identifier>
                    <ScaleDenominator>{matrix.scaleDenominator}</ScaleDenominator>
                    <TopLeftCorner>{matrix.topLeftCorner[0]} {matrix.topLeftCorner[1]}</TopLeftCorner>
                    <TileWidth>{matrix.tileWidth}</TileWidth>
                    <TileHeight>{matrix.tileHeight}</TileHeight>
                    <MatrixWidth>{matrix.matrixWidth}</MatrixWidth>
                    <MatrixHeight>{matrix.matrixHeight}</MatrixHeight>
                </TileMatrix>"""
        tileMatrix.append(tm)

    return templates.TemplateResponse(
        "wmts.xml",
        {
            "request": request,
            "tiles_endpoint": tiles_url,
            "bounds": bounds,
            "tileMatrix": tileMatrix,
            "tms": tms,
            "title": "Cloud Optimized GeoTIFF",
            "layer_name": "cogeo",
            "media_type": tile_format.mediatype,
        },
        media_type=MediaType.xml.value,
    )

def point(reader: BaseReader, env: Dict, src_path: str, reader_params: Dict, lon: float, lat: float, layer_params, dataset_params):
    """Get Point value for a dataset."""
    with rasterio.Env(**env):
        with reader(src_path, **reader_params) as src_dst:
            values = src_dst.point(
                lon,
                lat,
                **layer_params,
                **dataset_params,
            )
            return {"coordinates": [lon, lat], "values": values}


def preview(
    reader: BaseReader,
    format: ImageType,
    src_path,
    preview_params,
    postprocess_params,
    colormap,
    render_params,
    reader_params,
    env: Dict,
):
    """Create preview of a dataset."""
    timings = []

    with Timer() as t:
        with rasterio.Env(**env):
            with reader(src_path, **reader_params) as src_dst:
                data = src_dst.preview(
                    **preview_params
                )
                dst_colormap = getattr(src_dst, "colormap", None)
    timings.append(("dataread", round(t.elapsed * 1000, 2)))

    if not format:
        format = ImageType.jpeg if data.mask.all() else ImageType.png

    with Timer() as t:
        image = data.post_process(**postprocess_params)
    timings.append(("postprocess", round(t.elapsed * 1000, 2)))

    with Timer() as t:
        content = image.render(
            img_format=format.driver,
            colormap=colormap or dst_colormap,
            **format.profile,
            **render_params,
        )
    timings.append(("format", round(t.elapsed * 1000, 2)))

    return timings, content

def part(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    reader: BaseReader,
    format: ImageType,
    src_path,
    part_params,
    postprocess_params,
    colormap,
    render_params,
    reader_params,
    env: Dict,
):
    timings = []

    with Timer() as t:
        with rasterio.Env(**env):
            with reader(src_path, **reader_params) as src_dst:
                data = src_dst.part(
                    [minx, miny, maxx, maxy],
                    **part_params
                )
                dst_colormap = getattr(src_dst, "colormap", None)
    timings.append(("dataread", round(t.elapsed * 1000, 2)))

    with Timer() as t:
        image = data.post_process(**postprocess_params)
    timings.append(("postprocess", round(t.elapsed * 1000, 2)))

    with Timer() as t:
        content = image.render(
            img_format=format.driver,
            colormap=colormap or dst_colormap,
            **format.profile,
            **render_params,
        )
    timings.append(("format", round(t.elapsed * 1000, 2)))

    return timings, content

def geojson_crop(
    geojson: Feature,
    reader: BaseReader,
    format: ImageType,
    src_path,
    feature_params,
    postprocess_params,
    colormap,
    render_params,
    reader_params,
    env: Dict,
):
    """Create image from a geojson feature."""
    timings = []

    with Timer() as t:
        with rasterio.Env(**env):
            with reader(src_path, **reader_params) as src_dst:
                data = src_dst.feature(
                    geojson.dict(exclude_none=True),
                    **feature_params,
                )
                dst_colormap = getattr(src_dst, "colormap", None)
    timings.append(("dataread", round(t.elapsed * 1000, 2)))

    with Timer() as t:
        image = data.post_process(**postprocess_params)
    timings.append(("postprocess", round(t.elapsed * 1000, 2)))

    if not format:
        format = ImageType.jpeg if data.mask.all() else ImageType.png

    with Timer() as t:
        content = image.render(
            img_format=format.driver,
            colormap=colormap or dst_colormap,
            **format.profile,
            **render_params,
        )
    timings.append(("format", round(t.elapsed * 1000, 2)))
    return timings, content
