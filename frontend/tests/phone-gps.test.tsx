import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import PhoneGps from "@/components/map/PhoneGps";
import { api } from "@/lib/api";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { role: "driver" } }) }));
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }));

describe("phone GPS sharing", () => {
  let receive: PositionCallback;
  const clearWatch = vi.fn();
  const watchPosition = vi.fn((success: PositionCallback) => { receive = success; return 12; });

  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue([{ id: 1, registration_number: "MP01" }]);
    vi.mocked(api.post).mockResolvedValue({ accepted: 1 });
    Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
    Object.defineProperty(navigator, "geolocation", { value: { watchPosition, clearWatch }, configurable: true });
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("requires consent, sends a location, then stops and ignores late callbacks", async () => {
    render(<PhoneGps />);
    await screen.findByText("MP01");
    const start = screen.getByRole("button", { name: /start phone gps/i });
    expect(start).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(start);
    expect(watchPosition).toHaveBeenCalledTimes(1);
    await act(async () => {
      receive({ timestamp: Date.now(), coords: { latitude: 23, longitude: 77, accuracy: 10, speed: null, heading: null } } as GeolocationPosition);
    });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/gps/phone", expect.objectContaining({ vehicle_id: 1, latitude: 23, speed_kph: null })));
    fireEvent.click(screen.getByRole("button", { name: /stop sharing/i }));
    expect(clearWatch).toHaveBeenCalledWith(12);
    await act(async () => { receive({ timestamp: Date.now(), coords: { latitude: 24, longitude: 78, accuracy: 10 } } as GeolocationPosition); });
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("clears the location watch when unmounted", async () => {
    const { unmount } = render(<PhoneGps />);
    await screen.findByText("MP01");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /start phone gps/i }));
    unmount();
    expect(clearWatch).toHaveBeenCalledWith(12);
  });
});
