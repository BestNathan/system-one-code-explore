export async function loadUser(id: string) {
  const response = await fetch(`/api/users/${id}`);
  return response.json();
}
