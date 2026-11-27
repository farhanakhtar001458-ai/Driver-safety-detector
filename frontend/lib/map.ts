/** Validate coordinates without treating the equator or prime meridian as missing. */
export function validCoordinates(latitude: unknown, longitude: unknown): latitude is number {
  return typeof latitude === "number" && Number.isFinite(latitude) && latitude >= -90 && latitude <= 90 &&
    typeof longitude === "number" && Number.isFinite(longitude) && longitude >= -180 && longitude <= 180;
}
